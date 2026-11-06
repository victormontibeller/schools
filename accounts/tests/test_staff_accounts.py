"""Regressões de ativação e continuidade da administração escolar."""

import pytest

from accounts.invitation_tokens import InvitationTokenService
from accounts.services import AccountService
from accounts.staff_services import STAFF_INVITE_SALT, StaffAccountService
from audit.models import AuditLog
from base.exceptions import BusinessRuleViolationError, PermissionDeniedError
from core.models import CustomUser, Role


@pytest.fixture(autouse=True)
def invitation_school(db):
    from tenancy.models import Domain, School

    school, _ = School.objects.get_or_create(
        schema_name="test_school", defaults={"name": "Fictícia"}
    )
    Domain.objects.get_or_create(
        domain="school.example.test", defaults={"tenant": school, "is_primary": True}
    )
    return school


@pytest.mark.django_db
def test_create_staff_invitation_rotates_token_and_activates_once(user):
    from notifications.models import MessageLog

    role = Role.objects.get_or_create(name=Role.Name.SECRETARY)[0]
    service = StaffAccountService(user=user)
    invited = service.create_staff_user(
        {
            "first_name": "Equipe",
            "last_name": "Piloto",
            "email": "equipe@example.test",
            "role_name": role.name,
        }
    )
    service.send_staff_invitation(invited.pk)
    links = [
        log.payload["scope"]["invitation_token"]
        for log in MessageLog.objects.filter(source_type="account_invitation").order_by(
            "created_at"
        )
    ]
    assert len(links) == 2
    assert not invited.is_active
    assert not invited.has_usable_password()
    with pytest.raises(BusinessRuleViolationError):
        StaffAccountService().activate_staff_invitation(links[0], "Violeta824")
    active = StaffAccountService().activate_staff_invitation(links[1], "Violeta824")
    assert active.check_password("Violeta824")
    with pytest.raises(BusinessRuleViolationError):
        StaffAccountService().activate_staff_invitation(links[1], "Violeta824")
    assert AuditLog.objects.filter(model_name="CustomUser", object_id=str(active.pk)).count() >= 4


@pytest.mark.django_db
def test_deactivate_last_administrator_rolls_back(user):
    with pytest.raises(BusinessRuleViolationError):
        AccountService(user=user).deactivate_user(user.pk)
    user.refresh_from_db()
    assert user.is_active
    assert user.deleted_at is None
    second = CustomUser.objects.create_user(email="substitute@example.test", role=user.role)
    AccountService(user=user).deactivate_user(second.pk)
    second.refresh_from_db()
    assert not second.is_active
    with pytest.raises(BusinessRuleViolationError):
        AccountService(user=user).update_user(
            user.pk, {"is_active": False, "version": user.version}
        )


@pytest.mark.django_db
def test_create_staff_denies_non_administrator(user):
    role = Role.objects.get_or_create(name=Role.Name.SECRETARY)[0]
    actor = CustomUser.objects.create_user(email="secretary@example.test", role=role)
    with pytest.raises(PermissionDeniedError):
        StaffAccountService(user=actor).create_staff_user({})


@pytest.mark.django_db
def test_consume_invitation_rejects_changed_tenant(user):
    from base import context

    invited = CustomUser.objects.create_user(
        email="pending@example.test", role=user.role, is_active=False
    )
    token = InvitationTokenService().issue_token(invited.pk, salt=STAFF_INVITE_SALT)
    previous = context.current_tenant.set("other_school")
    try:
        with pytest.raises(BusinessRuleViolationError):
            StaffAccountService().activate_staff_invitation(token, "Violeta824")
    finally:
        context.current_tenant.reset(previous)
    invited.refresh_from_db()
    assert not invited.is_active


@pytest.mark.django_db
def test_update_email_revokes_invitation_and_rejects_manual_activation(user):
    invited = CustomUser.objects.create_user(
        email="before@example.test", role=user.role, is_active=False
    )
    token = InvitationTokenService().issue_token(invited.pk, salt=STAFF_INVITE_SALT)
    invited.refresh_from_db()
    AccountService(user=user).update_user(
        invited.pk, {"email": "after@example.test", "version": invited.version}
    )
    with pytest.raises(BusinessRuleViolationError):
        StaffAccountService().activate_staff_invitation(token, "Violeta824")
    invited.refresh_from_db()
    with pytest.raises(BusinessRuleViolationError):
        AccountService(user=user).update_user(
            invited.pk, {"is_active": True, "version": invited.version}
        )
    invited.refresh_from_db()
    assert not invited.is_active


@pytest.mark.django_db
def test_staff_create_and_invitation_work_without_javascript(client, user):
    from django.urls import reverse

    from notifications.models import MessageLog

    client.force_login(user)
    assert client.get(reverse("staff_user_create")).status_code == 200
    response = client.post(
        reverse("staff_user_create"),
        {
            "first_name": "Equipe",
            "last_name": "Piloto",
            "email": "native@example.test",
            "role_name": "SECRETARY",
        },
    )
    assert response.status_code == 302
    token = MessageLog.objects.get(source_type="account_invitation").payload["scope"][
        "invitation_token"
    ]
    client.logout()
    response = client.post(
        reverse("staff_invitation"),
        {"token": token, "password": "Violeta824", "password_confirm": "Violeta824"},
    )
    assert response.status_code == 302
    assert CustomUser.objects.get(email="native@example.test").is_active


@pytest.mark.django_db
def test_reissued_staff_invitation_preserves_identity_until_valid_activation(client, user):
    from django.urls import reverse

    from notifications.models import MessageLog

    invited = StaffAccountService(user=user).create_staff_user(
        {
            "first_name": "Equipe",
            "last_name": "Piloto",
            "email": "resend@example.test",
            "role_name": "SECRETARY",
        }
    )
    deliveries = MessageLog.objects.filter(source_type="account_invitation").order_by("created_at")
    previous_token = deliveries.get().payload["scope"]["invitation_token"]
    client.force_login(user)
    response = client.post(reverse("staff_user_invite", args=[invited.pk]))
    assert response.status_code == 302
    assert response.url == reverse("user_detail", args=[invited.pk])
    assert deliveries.count() == 2
    current_token = deliveries.last().payload["scope"]["invitation_token"]
    assert current_token != previous_token
    invited.refresh_from_db()
    nonce = invited.invitation_nonce
    client.logout()

    for token, password, error_field in (
        (previous_token, "Violeta824", "__all__"),
        (current_token, "123", "password"),
    ):
        response = client.post(
            reverse("staff_invitation"),
            {"token": token, "password": password, "password_confirm": password},
        )
        assert response.status_code == 200
        assert error_field in response.context["form"].errors
        invited.refresh_from_db()
        assert not invited.is_active
        assert not invited.has_usable_password()
        assert invited.invitation_nonce == nonce

    response = client.post(
        reverse("staff_invitation"),
        {"token": current_token, "password": "Violeta824", "password_confirm": "Violeta824"},
    )
    assert response.status_code == 302
    assert response.url == reverse("login")
    invited.refresh_from_db()
    assert invited.is_active
    assert invited.check_password("Violeta824")
    client.force_login(user)
    response = client.post(reverse("staff_user_invite", args=[invited.pk]), follow=True)
    assert response.status_code == 200
    assert "Utilize recuperar senha." in response.content.decode()
    assert deliveries.count() == 2
    invited.refresh_from_db()
    assert invited.invitation_nonce == nonce


@pytest.mark.django_db
def test_staff_form_rejects_duplicate_inactive_identity_without_side_effects(client, user):
    from django.urls import reverse

    from notifications.models import MessageLog

    existing = CustomUser.objects.create_user(
        email="reserved@example.test", role=Role.objects.get(name="SECRETARY"), is_active=False
    )
    before = (CustomUser.all_objects.count(), MessageLog.objects.count(), AuditLog.objects.count())
    client.force_login(user)
    response = client.post(
        reverse("staff_user_create"),
        {
            "first_name": "Equipe",
            "last_name": "Duplicada",
            "email": "RESERVED@example.test",
            "role_name": "FINANCE",
        },
    )
    assert response.status_code == 200
    assert "email" in response.context["form"].errors
    assert before == (
        CustomUser.all_objects.count(),
        MessageLog.objects.count(),
        AuditLog.objects.count(),
    )
    existing.refresh_from_db()
    assert not existing.is_active
    assert existing.role.name == "SECRETARY"
    assert existing.invitation_nonce is None
