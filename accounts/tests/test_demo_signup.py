"""Testes do ciclo de vida das contas temporárias DEMO."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services import AccountService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError


@pytest.mark.django_db
def test_create_demo_user_starts_inactive_and_schedules_verification(
    django_capture_on_commit_callbacks,
):
    """Conta só autentica depois de confirmar o e-mail."""
    with patch("accounts.tasks.send_demo_verification_task.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            user = AccountService().create_demo_user(
                {
                    "first_name": "Visitante",
                    "last_name": "Demo",
                    "email": "visitor@example.com",
                    "password": "Violeta824",
                },
                lambda token: f"https://demo.localhost/demo/verificar/{token}/",
            )
    assert user.is_active is False
    assert user.email_verified_at is None
    delay.assert_called_once()


@pytest.mark.django_db
def test_verify_demo_user_activates_for_seven_days():
    """Confirmação ativa a conta temporariamente."""
    with patch("accounts.tasks.send_demo_verification_task.delay"):
        user = AccountService().create_demo_user(
            {
                "first_name": "Visitante",
                "last_name": "Demo",
                "email": "verified@example.com",
                "password": "Violeta824",
            },
            lambda token: token,
        )
        from django.core import signing

        from accounts.services import DEMO_VERIFY_SALT

        token = signing.dumps({"user_id": str(user.pk)}, salt=DEMO_VERIFY_SALT, compress=True)
        verified = AccountService().verify_demo_user(token)
    assert verified.is_active is True
    assert verified.email_verified_at is not None
    assert verified.expires_at - verified.email_verified_at == timedelta(days=7)


@pytest.mark.django_db
def test_expire_demo_users_anonymizes_and_soft_deletes():
    """Expiração remove PII sem delete físico."""
    from core.models import CustomUser

    user = CustomUser.objects.create_user(
        email="expired@example.com",
        password="Senha123",
        first_name="Expired",
        last_name="Visitor",
        access_mode=CustomUser.AccessMode.DEMO,
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    assert AccountService().expire_demo_users() == 1
    user = CustomUser.all_objects.get(pk=user.pk)
    assert user.deleted_at is not None
    assert user.email.endswith("@anonymous.invalid")


@pytest.mark.django_db
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
def test_demo_signup_throttles_sixth_attempt(client):
    """O limite por IP bloqueia novas criações durante uma hora."""
    cache.set("demo-signup:127.0.0.1", 5, timeout=3600)
    with patch("accounts.services.AccountService.create_demo_user") as create:
        response = client.post(
            reverse("demo_signup"),
            {
                "first_name": "Visitante",
                "last_name": "Demo",
                "email": "limited@example.com",
                "password": "Senha123",
                "confirm_password": "Senha123",
            },
            REMOTE_ADDR="127.0.0.1",
        )
    assert response.status_code == 200
    assert "Limite de cadastros" in str(response.context["form"].non_field_errors())
    create.assert_not_called()


@pytest.mark.django_db
def test_demo_user_rejects_duplicate_and_verification_edge_cases():
    import uuid

    from django.core import signing

    from accounts.services import DEMO_VERIFY_SALT
    from core.models import CustomUser

    existing = CustomUser.objects.create_user(
        email="duplicate-demo@example.com",
        password="Senha123",
        access_mode=CustomUser.AccessMode.DEMO,
    )
    with pytest.raises(ValidationError):
        AccountService().create_demo_user(
            {
                "first_name": "Demo",
                "last_name": "Duplicado",
                "email": existing.email,
                "password": "Violeta824",
            },
            lambda token: token,
        )

    missing_token = signing.dumps(
        {"user_id": str(uuid.uuid4())}, salt=DEMO_VERIFY_SALT, compress=True
    )
    with pytest.raises(ObjectNotFoundError):
        AccountService().verify_demo_user(missing_token)
    with pytest.raises(BusinessRuleViolationError):
        AccountService().verify_demo_user("invalid")

    existing.email_verified_at = timezone.now()
    existing.save(update_fields=["email_verified_at", "updated_at"])
    used_token = signing.dumps({"user_id": str(existing.pk)}, salt=DEMO_VERIFY_SALT, compress=True)
    with pytest.raises(BusinessRuleViolationError):
        AccountService().verify_demo_user(used_token)
