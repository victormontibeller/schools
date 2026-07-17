"""Testes dos convites de acesso de responsáveis."""

from unittest.mock import patch

import pytest
from django.urls import reverse

from base.exceptions import BusinessRuleViolationError, ValidationError
from core.models import Role
from guardians.invitation_services import GuardianInvitationService
from guardians.models import Guardian


@pytest.fixture()
def guardian_contact(user):
    Role.objects.get_or_create(name=Role.Name.GUARDIAN)
    return Guardian.objects.create(
        first_name="Família",
        last_name="Teste",
        email="family-invite@test.com",
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
def test_send_invitation_creates_inactive_linked_account(
    user, guardian_contact, django_capture_on_commit_callbacks
):
    captured = {}
    with patch("guardians.tasks.send_guardian_invitation_task.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            account = GuardianInvitationService(user=user).send_invitation(
                guardian_contact.pk,
                lambda token: captured.setdefault("token", token) or "unused",
            )

    guardian_contact.refresh_from_db()
    assert guardian_contact.user == account
    assert account.is_active is False
    assert account.has_usable_password() is False
    assert captured["token"]
    delay.assert_called_once()


@pytest.mark.django_db
def test_activate_invitation_is_single_use(user, guardian_contact):
    captured = {}
    with patch("guardians.tasks.send_guardian_invitation_task.delay"):
        GuardianInvitationService(user=user).send_invitation(
            guardian_contact.pk,
            lambda token: captured.setdefault("token", token) or "unused",
        )

    account = GuardianInvitationService().activate_invitation(captured["token"], "Violeta824")

    assert account.is_active
    assert account.check_password("Violeta824")
    with pytest.raises(BusinessRuleViolationError):
        GuardianInvitationService().activate_invitation(captured["token"], "Violeta824")


@pytest.mark.django_db
def test_activate_invitation_rejects_expired_token(user, guardian_contact):
    captured = {}
    with (
        patch("guardians.tasks.send_guardian_invitation_task.delay"),
        patch("django.core.signing.time.time", return_value=1_000),
    ):
        GuardianInvitationService(user=user).send_invitation(
            guardian_contact.pk,
            lambda token: captured.setdefault("token", token) or "unused",
        )

    with (
        patch("django.core.signing.time.time", return_value=1_000 + 8 * 24 * 60 * 60),
        pytest.raises(BusinessRuleViolationError),
    ):
        GuardianInvitationService().activate_invitation(captured["token"], "Violeta824")


@pytest.mark.django_db
def test_send_invitation_requires_email(user):
    guardian = Guardian.objects.create(created_by=user, updated_by=user)

    with pytest.raises(ValidationError):
        GuardianInvitationService(user=user).send_invitation(guardian.pk, lambda token: token)


@pytest.mark.django_db
def test_guardian_invitation_view_activates_account(client, user, guardian_contact):
    captured = {}
    with patch("guardians.tasks.send_guardian_invitation_task.delay"):
        GuardianInvitationService(user=user).send_invitation(
            guardian_contact.pk,
            lambda token: captured.setdefault("token", token) or "unused",
        )

    response = client.post(
        reverse("guardian_invitation"),
        {
            "token": captured["token"],
            "password": "Violeta824",
            "password_confirm": "Violeta824",
        },
    )

    guardian_contact.refresh_from_db()
    assert response.status_code == 302
    assert guardian_contact.user.is_active
