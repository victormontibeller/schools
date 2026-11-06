"""Privacidade, calendário, resposta humana e ciclo de atendimento."""

import datetime as dt

import pytest
from freezegun import freeze_time

from accounts.services import AccountService
from base.exceptions import BusinessRuleViolationError, PermissionDeniedError
from core.models import CustomUser, Role, RoleModuleAccess
from guardians.models import Guardian, StudentGuardian
from service_requests.calendar_services import ResponseDeadline
from service_requests.configuration_services import ServiceConfigurationService
from service_requests.models import RequestMessage
from service_requests.selectors import ServiceRequestSelector
from service_requests.services import ServiceRequestService

pytestmark = pytest.mark.django_db


def open_ticket(setup):
    return ServiceRequestService(user=setup["family"]).create_request(
        {
            "subject": "Solicitação privada",
            "body": "Mensagem privada",
            "student_id": setup["student"].pk,
            "department_id": setup["department"].pk,
        }
    )


def test_reply_resolve_and_reopen_renews_only_first_human_response_deadline(user, setup_requests):
    with freeze_time("2026-10-23 14:00:00-03:00"):
        ticket = open_ticket(setup_requests)
    assert ticket.response_due_at == dt.datetime.fromisoformat("2026-10-26T18:00:00-03:00")
    staff = ServiceRequestService(user=setup_requests["staff"])
    ticket = staff.update_request_status(ticket.pk, version=ticket.version, status="IN_PROGRESS")
    assert ticket.first_response_at is None
    with pytest.raises(BusinessRuleViolationError):
        staff.update_request_status(ticket.pk, version=ticket.version, status="RESOLVED")
    staff.add_request_message(ticket.pk, version=ticket.version, body="Resposta humana")
    ticket.refresh_from_db()
    assert ticket.first_response_at and ticket.status == "WAITING_FAMILY"
    ticket = staff.update_request_status(ticket.pk, version=ticket.version, status="RESOLVED")
    with freeze_time("2026-10-27 19:00:00-03:00"):
        ticket = ServiceRequestService(user=setup_requests["family"]).reopen_request(
            ticket.pk, version=ticket.version
        )
    assert ticket.cycle == 2 and ticket.first_response_at is None
    assert ticket.response_due_at == dt.datetime.fromisoformat("2026-10-28T18:00:00-03:00")
    assert RequestMessage.objects.filter(request=ticket).count() == 2


def test_calendar_skips_weekends_and_explicit_administrative_closures(user, setup_requests):
    calendar = setup_requests["calendar"]
    calendar.closed_dates = ["2026-10-26"]
    calendar.save()
    for opened in [
        "2026-10-23T08:00:00-03:00",
        "2026-10-24T19:00:00-03:00",
        "2026-10-25T18:00:00-03:00",
    ]:
        assert ResponseDeadline.calculate(
            dt.datetime.fromisoformat(opened)
        ) == dt.datetime.fromisoformat("2026-10-27T18:00:00-03:00")


def test_other_guardian_of_same_child_cannot_read_and_guard_revocation_closes_access(
    user, setup_requests
):
    ticket = open_ticket(setup_requests)
    account = CustomUser.objects.create_user(
        email="other@example.test", role=Role.objects.get(name="GUARDIAN")
    )
    guardian = Guardian.objects.create(user=account)
    StudentGuardian.objects.create(guardian=guardian, student=ticket.student, has_custody=True)
    with pytest.raises(PermissionDeniedError):
        ServiceRequestSelector().get_for_user(ticket.pk, account)
    link = setup_requests["link"]
    link.has_custody = False
    link.save()
    with pytest.raises(PermissionDeniedError):
        ServiceRequestSelector().get_for_user(ticket.pk, setup_requests["family"])


def test_last_attendant_cannot_be_removed_deactivated_or_have_role_changed(user, setup_requests):
    staff, department = setup_requests["staff"], setup_requests["department"]
    with pytest.raises(BusinessRuleViolationError):
        AccountService(user=user).deactivate_user(staff.pk)
    with pytest.raises(BusinessRuleViolationError):
        AccountService(user=user).update_user(
            staff.pk, {"role_id": Role.objects.get(name="FINANCE").pk}
        )
    with pytest.raises(BusinessRuleViolationError):
        ServiceConfigurationService(user=user).update_department(
            "SECRETARY", enabled=True, user_ids=[], version=department.version
        )
    staff.refresh_from_db()
    assert staff.is_active


def test_transfer_preserves_deadline_and_revokes_previous_sector(user, setup_requests):
    finance = CustomUser.objects.create_user(
        email="finance@example.test", password="Violeta824", role=Role.objects.get(name="FINANCE")
    )
    target = ServiceConfigurationService(user=user).update_department(
        "FINANCE", enabled=True, user_ids=[str(finance.pk)], version=0
    )
    ticket = open_ticket(setup_requests)
    due = ticket.response_due_at
    ticket = ServiceRequestService(user=user).transfer_request(
        ticket.pk, version=ticket.version, department_id=target.pk
    )
    assert ticket.response_due_at == due
    with pytest.raises(PermissionDeniedError):
        ServiceRequestSelector().get_for_user(ticket.pk, setup_requests["staff"])
    assert ServiceRequestSelector().get_for_user(ticket.pk, finance)


def test_stale_admin_instance_cannot_write_after_loss_of_admin_and_edit(user, setup_requests):
    ticket = open_ticket(setup_requests)
    stale = CustomUser.objects.get(pk=user.pk)
    user.is_superuser = False
    user.role = Role.objects.get(name="SECRETARY")
    user.save()
    from service_requests.models import DepartmentMembership

    DepartmentMembership.objects.create(department=setup_requests["department"], user=user)
    access = RoleModuleAccess.objects.get(role=user.role, module_key="requests_secretary")
    access.can_edit = False
    access.save()
    with pytest.raises(PermissionDeniedError):
        ServiceRequestService(user=stale).add_request_message(
            ticket.pk, version=ticket.version, body="Proibido"
        )
    assert ticket.messages.count() == 1
