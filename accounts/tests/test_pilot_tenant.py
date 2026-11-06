"""Concorrência de administradores em conexões PostgreSQL separadas."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connection, connections
from django.test import TransactionTestCase

from accounts.services import AccountService
from base import context
from base.exceptions import BusinessRuleViolationError
from core.models import CustomUser, Role
from tenancy.models import School

pytestmark = pytest.mark.tenant


@pytest.mark.skipif(os.environ.get("DJANGO_ENV") != "test_pg", reason="Requer PostgreSQL")
class TestPilotAdministratorConcurrency(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        cls.tenant = School(schema_name="pilot_admin_race", name="Piloto fictício")
        cls.tenant.save(verbosity=0)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.tenant.delete(force_drop=True)
        super().tearDownClass()

    def test_deactivation_race_preserves_one_administrator(self):
        connection.set_tenant(self.tenant)
        role = Role.objects.get(name="ADMIN")
        users = [
            CustomUser.objects.create_user(
                email=f"admin{index}@example.test", password="Violeta824", role=role
            )
            for index in range(2)
        ]
        barrier = Barrier(2)

        def deactivate(index):
            conn = connections["default"]
            conn.set_tenant(self.tenant)
            token = context.current_tenant.set(self.tenant.schema_name)
            try:
                actor = CustomUser.objects.get(pk=users[index].pk)
                barrier.wait(timeout=10)
                try:
                    AccountService(user=actor).deactivate_user(actor.pk)
                    return "deactivated"
                except BusinessRuleViolationError:
                    return "blocked"
            finally:
                context.current_tenant.reset(token)
                conn.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sorted(executor.map(deactivate, range(2))) == ["blocked", "deactivated"]
        assert CustomUser.objects.filter(is_active=True, role=role).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(os.environ.get("DJANGO_ENV") != "test_pg", reason="Requer PostgreSQL")
def test_bootstrap_keeps_public_operator_out_of_tenant_identity():
    from unittest.mock import patch

    from accounts.staff_services import StaffAccountService
    from audit.models import AuditLog
    from base.context import tenant_schema_context
    from notifications.models import MessageLog
    from tenancy.models import Domain
    from tenancy.services import PlatformSchoolService

    connection.set_schema_to_public()
    operator = CustomUser.objects.create_user(
        email="operator@example.test", password="Violeta824", is_superuser=True
    )
    school = School(
        schema_name="pilot_bootstrap",
        name="Escola fictícia",
        settings={
            "email": {"resend_verified": True, "from_email": "school@example.test"},
        },
    )
    school.save(verbosity=0)
    Domain.objects.create(domain="pilot-bootstrap.localhost", tenant=school, is_primary=True)
    try:
        with patch("notifications.outbox_services.publish_task_after_commit"):
            admin_id = PlatformSchoolService(user=operator).create_school_administrator(
                school.pk,
                {"first_name": "Admin", "last_name": "Piloto", "email": "admin@example.test"},
            )
        assert AuditLog.objects.filter(user=operator, object_id=str(school.pk)).exists()
        with tenant_schema_context(school.schema_name):
            administrator = CustomUser.objects.get(pk=admin_id)
            assert administrator.created_by_id is None
            assert not administrator.is_active
            assert AuditLog.objects.filter(object_id=admin_id, user__isnull=True).exists()
            invite = MessageLog.objects.get(source_type="account_invitation").payload["scope"][
                "invitation_token"
            ]
            StaffAccountService().activate_staff_invitation(invite, "Violeta824")
        with pytest.raises(BusinessRuleViolationError):
            PlatformSchoolService(user=operator).create_school_administrator(
                school.pk,
                {"first_name": "Outro", "last_name": "Piloto", "email": "other@example.test"},
            )
    finally:
        connection.set_schema_to_public()
        school.delete(force_drop=True)
