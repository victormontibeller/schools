"""Configuração nativa, atribuição e conflitos com retorno compreensível."""

import pytest
from django.urls import reverse

from core.models import CustomUser, Role
from service_requests.models import AdministrativeCalendar
from service_requests.tests.test_workflow import open_ticket

pytestmark = pytest.mark.django_db


def test_admin_configures_calendar_and_rejects_invalid_or_unstaffed_sector(
    user, setup_requests, client
):
    url = reverse("service_request_configuration")
    client.force_login(setup_requests["family"])
    assert client.get(url).status_code == 403
    client.force_login(user)
    response = client.get(url)
    assert response.status_code == 200
    assert "Contato imediato" in response.content.decode()
    calendar = setup_requests["calendar"]
    payload = {
        "action": "calendar",
        "version": calendar.version,
        "weekdays": ["0", "1", "2", "3", "4"],
        "opens_at": "08:00",
        "closes_at": "18:00",
        "closed_dates": "inválida",
        "immediate_contact": "0000",
    }
    response = client.post(url, payload)
    assert response.status_code == 200
    calendar.refresh_from_db()
    assert not calendar.closed_dates
    payload["closed_dates"] = "2026-12-25"
    assert client.post(url, payload).status_code == 302
    assert AdministrativeCalendar.objects.get().closed_dates == ["2026-12-25"]
    response = client.post(
        url,
        {
            "action": "department",
            "code": "SECRETARY",
            "enabled": "on",
            "version": setup_requests["department"].version,
        },
    )
    assert response.status_code == 200
    assert "Um setor habilitado exige" in response.content.decode()
    assert setup_requests["department"].memberships.count() == 1
    response = client.post(
        url,
        {
            "action": "department",
            "code": "SECRETARY",
            "enabled": "on",
            "version": setup_requests["department"].version,
            "user_ids": [str(setup_requests["staff"].pk)],
        },
    )
    assert response.status_code == 302


def test_staff_assigns_and_handles_stale_reply_without_mutating_ticket(
    user, setup_requests, client
):
    ticket = open_ticket(setup_requests)
    client.force_login(setup_requests["staff"])
    url = reverse("service_request_action", args=[ticket.pk])
    response = client.post(
        url,
        {"action": "assign", "version": ticket.version, "attendant_id": setup_requests["staff"].pk},
    )
    assert response.status_code == 302
    stale = ticket.version
    ticket.refresh_from_db()
    assert ticket.attendant_id == setup_requests["staff"].pk
    response = client.post(
        reverse("service_request_respond", args=[ticket.pk]),
        {"version": stale, "body": "Formulário antigo"},
        follow=True,
    )
    assert "Recarregue" in response.content.decode()
    assert ticket.messages.count() == 1
    response = client.post(
        url, {"action": "status", "version": ticket.version, "status": "IN_PROGRESS"}
    )
    assert response.status_code == 302
    ticket.refresh_from_db()
    assert ticket.status == "IN_PROGRESS" and ticket.first_response_at is None
    outsider = CustomUser.objects.create_user(
        email="outside@example.test", password="Violeta824", role=Role.objects.get(name="SECRETARY")
    )
    response = client.post(
        url,
        {"action": "assign", "version": ticket.version, "attendant_id": outsider.pk},
        follow=True,
    )
    assert ticket.messages.count() == 1
    ticket.refresh_from_db()
    assert ticket.attendant_id != outsider.pk
    response = client.post(url, {"action": "unknown", "version": ticket.version}, follow=True)
    assert response.status_code == 200
    response = client.get(
        reverse("service_request_list"), {"q": ticket.protocol}, HTTP_HX_REQUEST="true"
    )
    assert ticket.protocol.encode() in response.content


def test_overdue_badge_clears_when_family_cancels_request(user, setup_requests, client):
    import datetime as dt

    from django.utils import timezone

    ticket = open_ticket(setup_requests)
    ticket.response_due_at = timezone.now() - dt.timedelta(days=1)
    ticket.save()
    client.force_login(setup_requests["family"])
    assert "Prazo vencido" in client.get(reverse("service_request_list")).content.decode()
    response = client.post(
        reverse("service_request_action", args=[ticket.pk]),
        {"action": "status", "version": ticket.version, "status": "CANCELLED"},
        follow=True,
    )
    assert response.status_code == 200 and not response.context["overdue"]
    assert "Prazo vencido" not in client.get(reverse("service_request_list")).content.decode()


def test_only_attendant_cannot_lose_base_edit_permission(user, setup_requests):
    from base.exceptions import BusinessRuleViolationError
    from core.access.services import AccessConfigurationService
    from core.models import RoleModuleAccess
    from core.tests.test_access_configuration import _current_matrix_state
    from service_requests.configuration_services import ServiceConfigurationService

    matrix, versions = _current_matrix_state()
    matrix["SECRETARY"]["service_requests"].discard("edit")
    with pytest.raises(BusinessRuleViolationError):
        AccessConfigurationService(user=user).update_access_matrix(matrix, versions)
    access = RoleModuleAccess.objects.get(
        role=setup_requests["staff"].role, module_key="service_requests"
    )
    assert access.can_edit
    access.can_edit = False
    access.save()
    with pytest.raises(BusinessRuleViolationError):
        ServiceConfigurationService(user=user).update_department(
            "SECRETARY",
            enabled=True,
            user_ids=[str(setup_requests["staff"].pk)],
            version=setup_requests["department"].version,
        )
