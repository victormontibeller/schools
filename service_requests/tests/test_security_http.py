"""Fluxo HTTP, arquivos privados, rollback e capacidade independente por setor."""

from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from audit.models import AuditLog
from audit.services import AuditService
from base.exceptions import BusinessRuleViolationError, PermissionDeniedError
from base.tests.images import png_upload
from core.access.services import AccessConfigurationService
from core.models import CustomUser, Role, RoleModuleAccess
from core.permissions import can_access
from notifications.models import MessageLog
from notifications.outbox_services import OutboxService
from service_requests.configuration_services import ServiceConfigurationService
from service_requests.event_services import RequestEventService
from service_requests.models import RequestAttachment, ServiceRequest
from service_requests.selectors import ServiceRequestSelector
from service_requests.services import ServiceRequestService
from service_requests.tests.test_workflow import open_ticket

pytestmark = pytest.mark.django_db


def test_family_opens_and_staff_replies_through_native_http(user, setup_requests, client):
    client.force_login(setup_requests["family"])
    response = client.post(
        reverse("service_request_create"),
        {
            "student_id": setup_requests["student"].pk,
            "department_id": setup_requests["department"].pk,
            "subject": "Assunto",
            "body": "Texto",
            "file": png_upload(),
        },
    )
    assert response.status_code == 302
    ticket = ServiceRequest.objects.get()
    response = client.get(response.url)
    assert response.status_code == 200
    assert b"0000-0000" in response.content and ticket.protocol.encode() in response.content
    assert client.get(reverse("service_request_list"), HTTP_HX_REQUEST="true").status_code == 200
    attachment = RequestAttachment.objects.get()
    assert (
        client.get(reverse("service_request_attachment", args=[attachment.pk])).status_code == 200
    )
    outsider = CustomUser.objects.create_user(
        email="outsider@example.test", password="Violeta824", role=Role.objects.get(name="GUARDIAN")
    )
    client.force_login(outsider)
    assert (
        client.get(reverse("service_request_attachment", args=[attachment.pk])).status_code == 403
    )
    client.force_login(setup_requests["staff"])
    response = client.post(
        reverse("service_request_respond", args=[ticket.pk]),
        {"body": "Resposta pública", "version": ticket.version},
    )
    assert response.status_code == 302
    ticket.refresh_from_db()
    assert ticket.first_response_at
    assert "Aguardando resposta da família" in client.get(response.url).content.decode()


def test_audit_failure_rolls_back_ticket_messages_intentions_and_upload(user, setup_requests):
    service = ServiceRequestService(user=setup_requests["family"])
    with patch.object(service, "_history", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            service.create_request(
                {
                    "student_id": setup_requests["student"].pk,
                    "department_id": setup_requests["department"].pk,
                    "subject": "Assunto",
                    "body": "Privado",
                },
                [png_upload()],
            )
    assert not ServiceRequest.objects.exists()
    assert not RequestAttachment.objects.exists()
    assert not MessageLog.objects.exists()
    assert all(not upload.storage.exists(upload.name) for upload in service._uploads)


def test_ticket_and_contact_are_redacted_from_audit_snapshots(user, setup_requests):
    ticket = open_ticket(setup_requests)
    ticket.subject = "Pessoa específica com informação pessoal"
    calendar = setup_requests["calendar"]
    calendar.immediate_contact = "private@example.test"
    AuditService(user=user).record_insert(ticket)
    AuditService(user=user).record_insert(calendar)
    ticket_audit = AuditLog.objects.filter(object_id=str(ticket.pk)).latest("created_at")
    calendar_audit = AuditLog.objects.filter(object_id=str(calendar.pk)).latest("created_at")
    assert ticket_audit.new_values["subject"] == "[REDACTED]"
    assert calendar_audit.new_values["immediate_contact"] == "[REDACTED]"


def test_overdue_notifies_staff_and_admin_once_without_repeating_to_family(user, setup_requests):
    ticket = open_ticket(setup_requests)
    import datetime as dt

    ticket.response_due_at = timezone.now() - dt.timedelta(days=1)
    ticket.save()
    service = RequestEventService()
    service.notify_overdue_request(ticket.pk)
    service.notify_overdue_request(ticket.pk)
    logs = MessageLog.objects.filter(
        source_type="service_requests", payload__event="request_overdue"
    )
    assert logs.count() == 4
    assert not logs.filter(recipient=setup_requests["family"]).exists()
    ticket.refresh_from_db()
    ServiceRequestService(user=setup_requests["staff"]).add_request_message(
        ticket.pk, version=ticket.version, body="Respondido"
    )
    with patch("notifications.channels.email.EmailChannel.send") as send:
        for log in logs.filter(channel="EMAIL"):
            OutboxService().dispatch(log.pk)
    send.assert_not_called()


def test_membership_does_not_grant_billing_access_and_matrix_cannot_remove_last_capacity(
    user, setup_requests
):
    staff = setup_requests["staff"]
    access = RoleModuleAccess.objects.get(role=staff.role, module_key="requests_finance")
    access.can_view = access.can_edit = True
    access.save()
    ServiceConfigurationService(user=user).update_department(
        "FINANCE", enabled=True, user_ids=[str(staff.pk)], version=0
    )
    staff = CustomUser.objects.get(pk=staff.pk)
    assert not can_access(staff, "finance_billings", "view")
    from core.access_catalog import ACTION_FIELDS, CONFIGURABLE_ROLES, MODULES

    roles = {r.name: r for r in Role.objects.filter(name__in=CONFIGURABLE_ROLES)}
    matrix = {
        role: {
            module.key: {
                a
                for a, f in ACTION_FIELDS.items()
                if getattr(RoleModuleAccess.objects.get(role=roles[role], module_key=module.key), f)
            }
            for module in MODULES
            if role in module.eligible_roles
        }
        for role in roles
    }
    matrix["SECRETARY"]["requests_secretary"] = {"view"}
    with pytest.raises(BusinessRuleViolationError):
        AccessConfigurationService(user=user).update_access_matrix(
            matrix, {name: r.version for name, r in roles.items()}
        )
    assert RoleModuleAccess.objects.get(role=staff.role, module_key="requests_secretary").can_edit


def test_admin_can_supervise_but_needs_sector_membership_to_reply(user, setup_requests):
    ticket = open_ticket(setup_requests)
    assert ServiceRequestSelector().get_for_user(ticket.pk, user)
    with pytest.raises(PermissionDeniedError):
        ServiceRequestService(user=user).add_request_message(
            ticket.pk, version=ticket.version, body="Resposta"
        )
    assert ticket.messages.count() == 1
