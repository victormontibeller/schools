"""Locks e privacidade do atendimento em conexões PostgreSQL independentes."""

import datetime as dt
import os
from unittest.mock import patch

import pytest
from django.db import connection

from accounts.services import AccountService
from accounts.staff_services import StaffAccountService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
from core.models import CustomUser, Role
from notifications.tests.test_announcement_workflow import family
from notifications.tests.test_outbox_tenant import outbox_tenant as tenant_fixture
from notifications.tests.test_outbox_tenant import race
from service_requests.configuration_services import ServiceConfigurationService
from service_requests.models import RequestMessage
from service_requests.selectors import ServiceRequestSelector
from service_requests.services import ServiceRequestService
from service_requests.tests.test_workflow import open_ticket

pg_tenant = tenant_fixture

pytestmark = [
    pytest.mark.tenant,
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(os.environ.get("DJANGO_ENV") != "test_pg", reason="Requer PostgreSQL"),
]


@pytest.fixture
def request_tenant(pg_tenant):
    school, delivery = pg_tenant
    admin = delivery.recipient
    account, _, _, links = family(admin)
    staff = [
        CustomUser.objects.create_user(
            email=f"staff{i}@example.test",
            password="Violeta824",
            role=Role.objects.get(name="SECRETARY"),
        )
        for i in range(2)
    ]
    config = ServiceConfigurationService(user=admin)
    config.update_calendar(
        {
            "version": 0,
            "weekdays": [0, 1, 2, 3, 4],
            "opens_at": dt.time(8),
            "closes_at": dt.time(18),
            "closed_dates": [],
            "immediate_contact": "0000",
        }
    )
    department = config.update_department(
        "SECRETARY", enabled=True, user_ids=[str(u.pk) for u in staff], version=0
    )
    with patch("notifications.outbox_services.publish_task_after_commit"):
        yield school, admin, staff, open_ticket(
            {"family": account, "student": links[0].student, "department": department}
        )


def test_concurrent_account_deactivation_keeps_one_capable_attendant(request_tenant):
    school, admin, staff, _ = request_tenant

    def deactivate(index):
        try:
            AccountService(user=CustomUser.objects.get(pk=admin.pk)).deactivate_user(
                staff[index].pk
            )
            return "done"
        except BusinessRuleViolationError:
            return "blocked"

    assert sorted(race(school, deactivate)) == ["blocked", "done"]
    assert CustomUser.objects.filter(pk__in=[u.pk for u in staff], is_active=True).count() == 1


def test_concurrent_replies_reject_stale_version_without_extra_message(request_tenant):
    school, _, staff, ticket = request_tenant

    def reply(index):
        try:
            ServiceRequestService(
                user=CustomUser.objects.get(pk=staff[index].pk)
            ).add_request_message(ticket.pk, version=ticket.version, body="Resposta humana")
            return "done"
        except BusinessRuleViolationError:
            return "conflict"

    assert sorted(race(school, reply)) == ["conflict", "done"]
    assert RequestMessage.objects.filter(request=ticket, is_staff_response=True).count() == 1


def test_request_identifier_does_not_cross_tenant_schema(request_tenant):
    from base.context import tenant_schema_context
    from tenancy.models import School

    school, _, _, ticket = request_tenant
    connection.set_schema_to_public()
    other = School(schema_name="request_other", name="Outra fictícia")
    other.save(verbosity=0)
    try:
        with tenant_schema_context(other.schema_name):
            admin = CustomUser.objects.create_user(
                email="admin@example.test",
                password="Violeta824",
                role=Role.objects.get(name="ADMIN"),
            )
            with pytest.raises(ObjectNotFoundError):
                ServiceRequestSelector().get_for_user(ticket.pk, admin)
    finally:
        connection.set_schema_to_public()
        other.delete(force_drop=True)
        connection.set_tenant(school)


def test_staff_invitation_reissue_locks_nullable_role_in_postgresql(pg_tenant):
    _, delivery = pg_tenant
    service = StaffAccountService(user=delivery.recipient)

    with patch("notifications.outbox_services.publish_task_after_commit"):
        account = service.create_staff_user(
            {
                "first_name": "Fictício",
                "last_name": "Piloto",
                "email": "pending@example.test",
                "role_name": "ADMIN",
            }
        )
        account.refresh_from_db()
        previous = account.invitation_nonce
        service.send_staff_invitation(account.pk)
    account.refresh_from_db()
    assert account.invitation_nonce != previous
