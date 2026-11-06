"""Recuperação auditada, não enumerável e limitada por escola e identidade opaca."""

import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.cache import caches
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.authentication_limits import AuthenticationLimit
from accounts.recovery_services import PasswordRecoveryService
from accounts.recovery_tokens import recovery_token_generator
from audit.models import AuditLog
from base.context import current_tenant
from base.exceptions import BusinessRuleViolationError, ValidationError
from tenancy.models import School

pytestmark = pytest.mark.django_db
PASSWORD = "NovaAurora824!"


@pytest.fixture
def recovery(user):
    School.objects.create(schema_name="test_school", name="Escola fictícia")
    return user, recovery_token_generator.make_token(user)


def confirm(user, token, password=PASSWORD):
    return PasswordRecoveryService().confirm_password_reset(
        user_id=user.pk, token=token, password=password, schema_name=current_tenant.get()
    )


def test_recovery_consumes_token_once_and_audits_without_password(recovery):
    user, token = recovery
    confirm(user, token)
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
    log = AuditLog.objects.filter(object_id=str(user.pk)).latest("created_at")
    assert "[REDACTED]" in json.dumps(log.old_values)
    assert PASSWORD not in json.dumps(log.new_values)
    assert user.password not in json.dumps(log.new_values)
    with pytest.raises(BusinessRuleViolationError):
        confirm(user, token)


def test_recovery_audit_failure_preserves_password_and_token(recovery):
    user, token = recovery
    old = user.password
    with patch.object(PasswordRecoveryService, "_record_audit", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            confirm(user, token)
    user.refresh_from_db()
    assert user.password == old
    assert recovery_token_generator.check_token(user, token)


@pytest.mark.parametrize("invalid", ["weak", "inactive", "school", "tenant", "token"])
def test_recovery_revalidates_every_condition_inside_service(recovery, invalid):
    user, token = recovery
    password = PASSWORD
    previous = None
    if invalid == "weak":
        password = "123"
    elif invalid == "inactive":
        user.is_active = False
        user.save()
    elif invalid == "school":
        School.objects.update(is_active=False)
    elif invalid == "tenant":
        School.objects.create(schema_name="other", name="Outra escola")
        previous = current_tenant.set("other")
    else:
        token = "invalid"
    try:
        with pytest.raises((BusinessRuleViolationError, ValidationError)):
            confirm(user, token, password)
    finally:
        if previous is not None:
            current_tenant.reset(previous)
    user.refresh_from_db()
    assert not user.check_password(PASSWORD)


def test_native_confirmation_uses_audited_command_and_handles_reused_link(client, recovery):
    user, token = recovery
    url = reverse(
        "password_reset_confirm", args=[urlsafe_base64_encode(force_bytes(user.pk)), token]
    )
    response = client.get(url)
    assert response.status_code == 302
    with patch.object(
        PasswordRecoveryService,
        "confirm_password_reset",
        wraps=PasswordRecoveryService().confirm_password_reset,
    ) as command:
        completed = client.post(
            response.url, {"new_password1": PASSWORD, "new_password2": PASSWORD}
        )
    assert completed.url == reverse("password_reset_complete")
    command.assert_called_once()
    expired = client.get(url)
    assert b"Solicitar novo link" in expired.content


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.parametrize("identity", ["existing", "missing", "inactive"])
def test_reset_response_and_limit_do_not_reveal_account(client, recovery, identity):
    user, _ = recovery
    email = user.email if identity != "missing" else "missing@example.test"
    if identity == "inactive":
        user.is_active = False
        user.save()
    for _ in range(3):
        response = client.post(reverse("password_reset"), {"email": email})
        assert response.status_code == 302
        assert response.url == reverse("password_reset_done")
    limited = client.post(reverse("password_reset"), {"email": email})
    assert limited.status_code == 429
    assert limited["Retry-After"] == "3600"
    assert len(mail.outbox) == (3 if identity == "existing" else 0)


def test_rate_limit_cache_failure_prevents_email(client, recovery):
    user, _ = recovery
    with (
        patch.object(caches["authentication"], "add", side_effect=ConnectionError),
        patch("notifications.channels.smtp_recovery.EmailMultiAlternatives.send") as send,
    ):
        response = client.post(reverse("password_reset"), {"email": user.email})
    assert response.status_code == 503
    assert response["Retry-After"] == "60"
    send.assert_not_called()


def test_rate_limit_is_atomic_scoped_and_contains_no_plain_identity():
    def reserve(_):
        marker = current_tenant.set("school_a")
        try:
            return AuthenticationLimit.reserve(
                scope="test", ip="192.0.2.1", recipient="person@example.test", limit=50
            )
        finally:
            current_tenant.reset(marker)

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(reserve, range(12)))
    assert sum(allowed for allowed, _ in outcomes) == 3
    marker = current_tenant.set("school_b")
    try:
        assert AuthenticationLimit.reserve(
            scope="test", ip="192.0.2.1", recipient="person@example.test"
        )[0]
    finally:
        current_tenant.reset(marker)
    keys = str(caches["authentication"]._cache.keys())
    for personal in ["192.0.2.1", "person@example.test", "school_a", "school_b"]:
        assert personal not in keys


def test_smtp_exception_is_generic_and_logs_no_recipient_or_token(client, recovery, caplog):
    from smtplib import SMTPRecipientsRefused

    caplog.set_level("WARNING", logger="notifications.channels.smtp_recovery")
    user, token = recovery
    failure = SMTPRecipientsRefused({user.email: (550, f"sensitive {token}")})
    with patch(
        "notifications.channels.smtp_recovery.EmailMultiAlternatives.send", side_effect=failure
    ):
        response = client.post(reverse("password_reset"), {"email": user.email})
    assert response.status_code == 302
    records = [record for record in caplog.records if record.name.endswith("smtp_recovery")]
    assert records
    for record in records:
        assert record.exc_info is None
        assert user.email not in record.getMessage()
        assert token not in record.getMessage()
        assert "sensitive" not in record.getMessage()
        from pythonjsonlogger.json import JsonFormatter

        rendered = JsonFormatter().format(record)
        assert user.email not in rendered and token not in rendered
