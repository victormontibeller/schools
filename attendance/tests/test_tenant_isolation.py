"""Concorrência do workflow de justificativas em PostgreSQL tenant-scoped."""

import datetime as dt
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connection, connections
from django.test import TransactionTestCase

from base import context
from core.models import CustomUser
from tenancy.models import Domain, School

pytestmark = [pytest.mark.tenant]

_requires_pg = pytest.mark.skipif(
    os.environ.get("DJANGO_ENV") != "test_pg",
    reason="Requer perfil DJANGO_ENV=test_pg (PostgreSQL + django_tenants)",
)


@_requires_pg
class TestAttendanceJustificationConcurrency(TransactionTestCase):
    """Garante uma única decisão quando aprovação e rejeição concorrem."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        cls.tenant = School(
            schema_name="attendance_concurrency",
            name="Frequência Concorrente",
        )
        cls.tenant.save(verbosity=0)
        cls.domain = Domain.objects.create(
            domain="attendance-concurrency.test.local",
            tenant=cls.tenant,
            is_primary=True,
        )
        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.domain.delete()
        cls.tenant.delete(force_drop=True)
        super().tearDownClass()

    def setUp(self):
        connection.set_tenant(self.tenant)
        self._ctx_token = context.current_tenant.set(self.tenant.schema_name)

    def tearDown(self):
        context.current_tenant.reset(self._ctx_token)

    def test_approve_and_reject_same_justification_are_serialized(self):
        from attendance.models import AttendanceJustification
        from attendance.services import AttendanceService
        from base.exceptions import BusinessRuleViolationError
        from students.models import Student

        actor = CustomUser.objects.create_user(
            email="attendance-lock@tenant.test",
            password="Senha123",
            is_superuser=True,
        )
        student = Student.objects.create(
            first_name="Aluno",
            last_name="Concorrente",
            birth_date=dt.date(2015, 1, 1),
            enrollment_number="ATTENDANCE-LOCK-STUDENT",
            created_by=actor,
            updated_by=actor,
        )
        justification = AttendanceJustification.objects.create(
            student=student,
            start_date=dt.date(2026, 8, 14),
            end_date=dt.date(2026, 8, 14),
            reason="Atendimento",
            created_by=actor,
            updated_by=actor,
        )
        barrier = Barrier(2)

        def run_in_connection(decision):
            thread_connection = connections["default"]
            thread_connection.set_tenant(self.tenant)
            token = context.current_tenant.set(self.tenant.schema_name)
            try:
                thread_actor = CustomUser.objects.get(pk=actor.pk)
                service = AttendanceService(user=thread_actor)
                barrier.wait()
                try:
                    if decision == "approve":
                        service.approve_justification(justification.pk)
                    else:
                        service.reject_justification(
                            justification.pk,
                            "Documento insuficiente",
                        )
                    return f"{decision}_completed"
                except BusinessRuleViolationError:
                    return f"{decision}_blocked"
            finally:
                context.current_tenant.reset(token)
                thread_connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run_in_connection, ("approve", "reject")))

        justification.refresh_from_db()
        assert sorted(result.rsplit("_", 1)[1] for result in results) == [
            "blocked",
            "completed",
        ]
        assert justification.status in {
            AttendanceJustification.Status.APPROVED,
            AttendanceJustification.Status.REJECTED,
        }
