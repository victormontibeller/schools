"""Convite familiar durável exige guarda atual em toda transição."""

import datetime as dt
from unittest.mock import patch

import pytest
from django.urls import reverse

from base.exceptions import BusinessRuleViolationError, ValidationError
from core.models import CustomUser, Role
from guardians.invitation_services import GuardianInvitationService
from guardians.models import Guardian, StudentGuardian
from notifications.models import MessageLog
from students.models import Student
from tenancy.models import Domain, School


@pytest.fixture()
def guardian_contact(user):
    Role.objects.get_or_create(name=Role.Name.GUARDIAN)
    school = School.objects.create(schema_name="test_school", name="Fictícia")
    Domain.objects.create(tenant=school, domain="school.example.test", is_primary=True)
    guardian = Guardian.objects.create(
        first_name="Família", last_name="Teste", email="family-invite@example.test"
    )
    student = Student.objects.create(
        first_name="Criança",
        last_name="Teste",
        birth_date=dt.date(2022, 1, 1),
        enrollment_number="INVITE-CHILD",
    )
    StudentGuardian.objects.create(guardian=guardian, student=student, has_custody=True)
    return guardian


def issue(user, guardian):
    account = GuardianInvitationService(user=user).send_invitation(guardian.pk)
    delivery = MessageLog.objects.filter(
        recipient=account, source_type="account_invitation"
    ).latest("created_at")
    return account, delivery.payload["scope"]["invitation_token"], delivery


@pytest.mark.django_db
def test_send_invitation_creates_inactive_linked_account(user, guardian_contact):
    account, token, delivery = issue(user, guardian_contact)
    guardian_contact.refresh_from_db()
    assert guardian_contact.user == account
    assert not account.is_active and not account.has_usable_password()
    assert token and delivery.dispatch_state == "PENDING"
    assert MessageLog.objects.filter(recipient=account).count() == 1


@pytest.mark.django_db
def test_activate_invitation_is_single_use(user, guardian_contact):
    _, token, _ = issue(user, guardian_contact)
    account = GuardianInvitationService().activate_invitation(token, "Violeta824")
    assert account.is_active and account.check_password("Violeta824")
    with pytest.raises(BusinessRuleViolationError):
        GuardianInvitationService().activate_invitation(token, "Violeta824")


@pytest.mark.django_db
def test_activate_invitation_rejects_expired_token(user, guardian_contact):
    with patch("django.core.signing.time.time", return_value=1_000):
        _, token, _ = issue(user, guardian_contact)
    with (
        patch("django.core.signing.time.time", return_value=1_000 + 8 * 24 * 60 * 60),
        pytest.raises(BusinessRuleViolationError),
    ):
        GuardianInvitationService().activate_invitation(token, "Violeta824")


@pytest.mark.django_db
def test_send_invitation_requires_email(user):
    guardian = Guardian.objects.create(created_by=user, updated_by=user)
    with pytest.raises(ValidationError):
        GuardianInvitationService(user=user).send_invitation(guardian.pk)


@pytest.mark.django_db
def test_send_invitation_denies_pickup_only_before_creating_identity(user, guardian_contact):
    StudentGuardian.objects.filter(guardian=guardian_contact).update(has_custody=False)
    before = CustomUser.objects.count()
    with pytest.raises(BusinessRuleViolationError):
        GuardianInvitationService(user=user).send_invitation(guardian_contact.pk)
    guardian_contact.refresh_from_db()
    assert guardian_contact.user_id is None
    assert CustomUser.objects.count() == before
    assert not MessageLog.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("revocation", ["custody", "student", "school"])
def test_invitation_revalidates_guard_and_school_at_send_and_consumption(
    user, guardian_contact, revocation
):
    from notifications.outbox_services import OutboxService

    account, token, delivery = issue(user, guardian_contact)
    if revocation == "custody":
        StudentGuardian.objects.filter(guardian=guardian_contact).update(has_custody=False)
    elif revocation == "student":
        Student.objects.update(is_active=False)
    else:
        School.objects.update(is_active=False)
    with patch("notifications.channels.email.EmailChannel.send") as send:
        OutboxService().dispatch(delivery.pk)
    send.assert_not_called()
    with pytest.raises(BusinessRuleViolationError):
        GuardianInvitationService().activate_invitation(token, "Violeta824")
    account.refresh_from_db()
    assert not account.is_active


@pytest.mark.django_db
def test_guardian_invitation_view_activates_account(client, user, guardian_contact):
    _, token, _ = issue(user, guardian_contact)
    response = client.post(
        reverse("guardian_invitation"),
        {"token": token, "password": "Violeta824", "password_confirm": "Violeta824"},
    )
    guardian_contact.refresh_from_db()
    assert response.status_code == 302
    assert guardian_contact.user.is_active


@pytest.mark.django_db
def test_reissue_after_contact_correction_uses_new_address_and_revokes_old_token(
    user, guardian_contact
):
    from notifications.channels import ChannelResult
    from notifications.outbox_services import OutboxService

    _, old_token, old_delivery = issue(user, guardian_contact)
    from accounts.services import AccountService

    guardian_contact.refresh_from_db()
    AccountService(user=user).update_user(
        guardian_contact.user_id, {"email": "corrected@example.test"}
    )
    guardian_contact.refresh_from_db()
    with pytest.raises(BusinessRuleViolationError):
        GuardianInvitationService().activate_invitation(old_token, "Violeta824")
    account, new_token, new_delivery = issue(user, guardian_contact)
    with patch(
        "notifications.channels.email.EmailChannel.send",
        return_value=ChannelResult(
            success=True, channel="EMAIL", recipient_address="", provider_message_id="fixture"
        ),
    ) as send:
        OutboxService().dispatch(old_delivery.pk)
        OutboxService().dispatch(new_delivery.pk)
    send.assert_called_once()
    assert send.call_args.args[0] == "corrected@example.test"
    assert new_token in __import__("urllib.parse", fromlist=["unquote"]).unquote(
        send.call_args.args[2]
    )
    assert account.email == "corrected@example.test"


@pytest.mark.django_db
def test_linked_guardian_contact_cannot_bypass_account_identity_command(user, guardian_contact):
    from guardians.services import GuardianService

    account, _, _ = issue(user, guardian_contact)
    old = account.email
    with pytest.raises(BusinessRuleViolationError):
        GuardianService(user=user).update_guardian(
            guardian_contact.pk, {"email": "wrong-path@example.test"}
        )
    guardian_contact.refresh_from_db()
    account.refresh_from_db()
    assert account.email == guardian_contact.email == old
