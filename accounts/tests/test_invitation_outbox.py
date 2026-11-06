"""Convites persistem antes da fila, sem depender de preferências escolares."""

from unittest.mock import patch
from urllib.parse import unquote

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.invitation_tokens import InvitationTokenService
from accounts.services import AccountService
from accounts.staff_services import STAFF_INVITE_SALT
from audit.models import AuditLog
from core.models import CustomUser, Role
from notifications.channels import ChannelResult
from notifications.models import MessageLog
from notifications.outbox_services import OutboxService
from teachers.models import Teacher
from tenancy.models import Domain, School

pytestmark = pytest.mark.django_db


@pytest.fixture()
def school(user):
    school = School.objects.create(schema_name="test_school", name="Fictícia")
    Domain.objects.create(tenant=school, domain="school.example.test", is_primary=True)
    return school


def pending(user):
    return CustomUser.objects.create_user(
        email="pending@example.test", role=user.role, is_active=False
    )


def delivery(account):
    return MessageLog.objects.filter(recipient=account, source_type="account_invitation").latest(
        "created_at"
    )


def success():
    return ChannelResult(
        success=True, channel="EMAIL", recipient_address="", provider_message_id="fake-provider"
    )


def test_broker_failure_preserves_invitation_and_recovery_ignores_optout(
    user, school, django_capture_on_commit_callbacks
):
    account = pending(user)
    with (
        patch("notifications.outbox_tasks.deliver_outbox_task.delay", side_effect=ConnectionError),
        django_capture_on_commit_callbacks(execute=True),
    ):
        token = InvitationTokenService().issue_token(account.pk, salt=STAFF_INVITE_SALT)
    intention = delivery(account)
    assert intention.dispatch_state == "PENDING"
    with patch("notifications.channels.email.EmailChannel.send", return_value=success()) as send:
        OutboxService().dispatch(intention.pk)
        OutboxService().dispatch(intention.pk)
    send.assert_called_once()
    assert token in unquote(send.call_args.args[2])
    intention.refresh_from_db()
    assert intention.status == "SENT"
    assert token not in intention.payload["url"]
    assert token not in str(list(AuditLog.objects.values("old_values", "new_values")))


def test_old_issuance_is_revoked_and_suspension_blocks_current(user, school):
    account = pending(user)
    InvitationTokenService().issue_token(account.pk, salt=STAFF_INVITE_SALT)
    first = delivery(account)
    InvitationTokenService().issue_token(account.pk, salt=STAFF_INVITE_SALT)
    current = delivery(account)
    with patch("notifications.channels.email.EmailChannel.send") as send:
        OutboxService().dispatch(first.pk)
        school.is_active = False
        school.save()
        OutboxService().dispatch(current.pk)
    send.assert_not_called()
    first.refresh_from_db()
    current.refresh_from_db()
    assert first.dispatch_state == current.dispatch_state == "REVOKED"


def test_teacher_invitation_uses_canonical_token_path(user, school):
    account = CustomUser.objects.create_user(
        email="teacher@example.test",
        role=Role.objects.get_or_create(name="TEACHER")[0],
        is_active=False,
    )
    Teacher.objects.create(user=account, registration_number="INVITED")
    token = AccountService().create_teacher_invitation_token(account.pk)
    with patch("notifications.channels.email.EmailChannel.send", return_value=success()) as send:
        OutboxService().dispatch(delivery(account).pk)
    assert unquote(send.call_args.kwargs["action_url"]) == "https://school.example.test" + reverse(
        "teacher_invitation", kwargs={"token": token}
    )


def test_invitation_retry_preserves_identity_and_payload(user, school):
    account = pending(user)
    InvitationTokenService().issue_token(account.pk, salt=STAFF_INVITE_SALT)
    intention = delivery(account)
    with patch(
        "notifications.channels.email.EmailChannel.send", side_effect=[TimeoutError(), success()]
    ) as send:
        OutboxService().dispatch(intention.pk)
        intention.refresh_from_db()
        assert intention.dispatch_state == "RETRY"
        intention.next_attempt_at = timezone.now()
        intention.save()
        OutboxService().dispatch(intention.pk)
    assert send.call_args_list[0] == send.call_args_list[1]


def test_message_admin_never_exposes_token_or_accepts_changes(client, user, school):
    account = pending(user)
    token = InvitationTokenService().issue_token(account.pk, salt=STAFF_INVITE_SALT)
    intention = delivery(account)
    user.is_staff = True
    user.save()
    client.force_login(user)
    path = reverse("admin:notifications_messagelog_change", args=[intention.pk])
    response = client.get(path)
    # The tenant middleware also blocks Django admin; verify its own readonly view.
    assert response.status_code == 403
    from django.contrib import admin
    from django.test import RequestFactory

    request = RequestFactory().get(path)
    request.user = user
    response = admin.site._registry[MessageLog].change_view(request, str(intention.pk))
    response.render()
    assert response.status_code == 200
    assert token not in response.content.decode()
    assert client.post(path, {"payload": "{}", "status": "SENT"}).status_code == 403
    intention.refresh_from_db()
    assert intention.status == "PENDING"


def test_delayed_invitation_delivery_displays_original_expiration(user, school):
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    account = pending(user)
    InvitationTokenService().issue_token(account.pk, salt=STAFF_INVITE_SALT)
    account.refresh_from_db()
    expiry = account.invitation_expires_at.astimezone(ZoneInfo("America/Sao_Paulo")).strftime(
        "%d/%m/%Y às %H:%M"
    )
    with (
        patch(
            "notifications.outbox_services.timezone.now",
            return_value=timezone.now() + timedelta(days=2),
        ),
        patch("notifications.channels.email.EmailChannel.send", return_value=success()) as send,
    ):
        OutboxService().dispatch(delivery(account).pk)
    assert expiry in str(send.call_args)
