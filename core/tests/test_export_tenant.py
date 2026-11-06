"""Exportação PostgreSQL de dois schemas e histórico financeiro completo."""

import datetime as dt
import json
import os
import uuid
import zipfile
from unittest.mock import patch

import pytest
from django.db import connection

from base.context import tenant_schema_context
from core.export_services import SchoolExportService
from core.models import CustomUser, Role
from financeiro.services import FinanceService, PaymentService
from notifications.tests.test_outbox_tenant import outbox_tenant as outbox_tenant
from students.models import Student
from tenancy.models import Domain, School

pytestmark = [
    pytest.mark.tenant,
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(os.environ.get("DJANGO_ENV") != "test_pg", reason="Requer PostgreSQL"),
]


def test_export_two_schemas_preserves_reversed_allocations_without_cross_school_content(
    request, tmp_path
):
    first, delivery = request.getfixturevalue("outbox_tenant")
    actor = delivery.recipient
    tmp_path.chmod(0o700)
    with tenant_schema_context("public"):
        other = School(
            schema_name=f"export_{uuid.uuid4().hex[:10]}", name="ISOLATED-SCHOOL-SENTINEL"
        )
        other.save(verbosity=0)
        Domain.objects.create(tenant=other, domain="isolated.example.test", is_primary=True)
    try:
        with (
            tenant_schema_context(first.schema_name),
            patch("notifications.outbox_services.publish_task_after_commit"),
        ):
            student = Student.objects.create(
                first_name="Export",
                last_name="Synthetic",
                birth_date=dt.date(2022, 1, 1),
                enrollment_number="EXPORT",
            )
            billing = FinanceService(user=actor).create_ad_hoc_billing(
                {
                    "student_id": student.pk,
                    "amount": "100.00",
                    "description": "Synthetic",
                    "due_date": dt.date.today(),
                }
            )
            payments = PaymentService(user=actor)
            payment = payments.create_payment(
                allocations=[{"billing_id": billing.pk, "amount": "40.00"}],
                paid_date=dt.date.today(),
            )
            payments.confirm_payment(payment.pk)
            payments.reverse_payment(payment.pk, reason="Synthetic reversal")
            SchoolExportService(user=actor).create_school_export(tmp_path / "first.zip")
        with tenant_schema_context(other.schema_name):
            second = CustomUser.objects.create_user(
                email="admin@example.test",
                role=Role.objects.get(name="ADMIN"),
                password=uuid.uuid4().hex,
            )
            SchoolExportService(user=second).create_school_export(tmp_path / "second.zip")
        with zipfile.ZipFile(tmp_path / "first.zip") as archive:
            rows = [
                json.loads(row)
                for row in archive.read("data/financeiro.PaymentRecord.jsonl").splitlines()
            ]
            allocations = [
                json.loads(row)
                for row in archive.read("data/financeiro.PaymentAllocation.jsonl").splitlines()
            ]
            assert rows[0]["status"] == "REVERSED"
            assert rows[0]["reversal_reason"] == "Synthetic reversal"
            assert allocations[0]["amount"] == "40.00"
            assert "idempotency_key" not in rows[0]
            assert b"ISOLATED-SCHOOL-SENTINEL" not in b"".join(
                archive.read(name) for name in archive.namelist()
            )
        with zipfile.ZipFile(tmp_path / "second.zip") as archive:
            assert not archive.read("data/financeiro.PaymentRecord.jsonl")
            assert str(student.pk).encode() not in b"".join(
                archive.read(name) for name in archive.namelist()
            )
    finally:
        connection.set_schema_to_public()
        other.delete(force_drop=True)
