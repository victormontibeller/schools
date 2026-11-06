"""Retentativas, gerações humanas, revalidação e estados do provedor."""

import datetime as dt
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone

from notifications.channels import ChannelResult
from notifications.delivery_services import MessageDeliveryService
from notifications.models import MessageLog
from notifications.outbox_services import OutboxService
from notifications.tests.test_announcement_workflow import family, publish

pytestmark = pytest.mark.django_db


def delivery_for(user):
    account, guardian, _, _ = family(user)
    draft, _ = publish(user)
    return MessageLog.objects.get(announcement=draft, channel="EMAIL"), account, guardian


def success(provider="provider-1"):
    return ChannelResult(
        success=True, channel="EMAIL", recipient_address="", provider_message_id=provider
    )


def test_fencing_prevents_expired_worker_from_finishing_new_claim(user, school):
    delivery, _, _ = delivery_for(user)
    service = OutboxService()
    old = service.claim_delivery(delivery.pk)
    delivery.refresh_from_db()
    delivery.lease_until = timezone.now() - dt.timedelta(seconds=1)
    delivery.save()
    current = service.claim_delivery(delivery.pk)
    assert old.lease_token != current.lease_token
    service.finish_delivery(delivery.pk, old.lease_token, success())
    delivery.refresh_from_db()
    assert delivery.status == "PENDING"
    service.finish_delivery(delivery.pk, current.lease_token, success())
    delivery.refresh_from_db()
    assert delivery.status == "SENT"


@pytest.mark.parametrize("change", ["account", "consent", "email", "school"])
def test_dispatch_rechecks_changes_after_claim_before_network(user, school, change):
    delivery, account, guardian = delivery_for(user)
    claimed = OutboxService().claim_delivery(delivery.pk)
    if change == "account":
        account.is_active = False
        account.save()
    elif change == "consent":
        guardian.accepts_email_notifications = False
        guardian.save()
    elif change == "email":
        account.email = "changed@example.test"
        account.save()
    else:
        school.is_active = False
        school.save()
    with (
        patch.object(OutboxService, "claim_delivery", return_value=claimed),
        patch("notifications.channels.email.EmailChannel.send") as send,
    ):
        OutboxService().dispatch(delivery.pk)
    send.assert_not_called()
    delivery.refresh_from_db()
    assert delivery.dispatch_state == "REVOKED"


def test_failed_webhook_before_worker_result_is_terminal_and_reprocessable(user, school):
    delivery, _, _ = delivery_for(user)
    claim = OutboxService().claim_delivery(delivery.pk)
    MessageDeliveryService().process_resend_event(
        external_event_id="failed-1",
        event_type="email.failed",
        provider_message_id="provider-failed",
        message_log_id=str(delivery.pk),
        occurred_at=timezone.now(),
    )
    OutboxService().finish_delivery(
        delivery.pk,
        claim.lease_token,
        ChannelResult(success=False, channel="EMAIL", recipient_address="", retryable=True),
    )
    delivery.refresh_from_db()
    assert delivery.status == delivery.dispatch_state == "FAILED"
    assert OutboxService().claim_delivery(delivery.pk) is None
    successor = OutboxService(user=user).request_delivery_retry(delivery.pk)
    assert successor.pk != delivery.pk
    assert successor.previous_delivery_id == delivery.pk
    assert successor.generation == 2
    assert OutboxService(user=user).request_delivery_retry(delivery.pk).pk == successor.pk


def test_reprocess_uses_new_destination_and_preserves_old_attempt(user, school):
    delivery, account, _ = delivery_for(user)
    with patch(
        "notifications.channels.email.EmailChannel.send",
        return_value=ChannelResult(
            success=False,
            channel="EMAIL",
            recipient_address="",
            error_message="invalid_address",
            retryable=False,
        ),
    ):
        OutboxService().dispatch(delivery.pk)
    account.email = "corrected@example.test"
    account.save()
    successor = OutboxService(user=user).request_delivery_retry(delivery.pk)
    with patch("notifications.channels.email.EmailChannel.send", return_value=success()) as send:
        OutboxService().dispatch(successor.pk)
    assert send.call_args.args[0] == "corrected@example.test"
    assert send.call_args.kwargs["idempotency_key"] == f"message-log/{successor.pk}"
    delivery.refresh_from_db()
    assert delivery.recipient_address != "corrected@example.test"
    assert delivery.status == "FAILED"


def test_sender_change_never_mutates_sdk_payload_under_same_key(user, school):
    delivery, _, _ = delivery_for(user)
    config = {
        "verified": True,
        "from_email": "old@example.test",
        "school_name": "Escola antiga",
        "domain": "example.test",
    }
    with (
        override_settings(RESEND_API_KEY="test_key"),
        patch("core.tenant_email.get_tenant_resend_config", side_effect=lambda: dict(config)),
        patch("resend.Emails.send", side_effect=[TimeoutError, {"id": "provider-new"}]) as sdk,
    ):
        OutboxService().dispatch(delivery.pk)
        delivery.refresh_from_db()
        delivery.next_attempt_at = timezone.now() - dt.timedelta(seconds=1)
        delivery.save()
        config["from_email"] = "new@example.test"
        config["school_name"] = "Escola nova"
        OutboxService().dispatch(delivery.pk)
        assert sdk.call_count == 1
        successor = OutboxService(user=user).request_delivery_retry(delivery.pk)
        OutboxService().dispatch(successor.pk)
    assert sdk.call_count == 2
    first, second = sdk.call_args_list
    assert first.args[0]["from"] == "Escola antiga <old@example.test>"
    assert second.args[0]["from"] == "Escola nova <new@example.test>"
    assert first.args[1]["idempotency_key"] != second.args[1]["idempotency_key"]


def test_sender_payload_is_redacted_from_audit(user, school):
    from audit.models import AuditLog

    delivery, _, _ = delivery_for(user)
    config = {"school_name": "Escola", "from_email": "sender@example.test"}
    with patch("core.tenant_email.get_tenant_resend_config", return_value=config):
        claimed = OutboxService().claim_delivery(delivery.pk)
    assert claimed.payload["sender_address"] == "Escola <sender@example.test>"
    audit = AuditLog.objects.filter(object_id=str(delivery.pk), operation="UPDATE").latest(
        "created_at"
    )
    assert audit.new_values["payload"]["sender_address"] == "[REDACTED]"
    assert "sender@example.test" not in str(audit.new_values)


@pytest.mark.parametrize("after_claim", [False, True])
def test_late_success_in_first_generation_cancels_third_generation(user, school, after_claim):
    original, _, _ = delivery_for(user)
    previous = original
    for _ in range(2):
        previous.dispatch_state = "FAILED"
        previous.save()
        previous = OutboxService(user=user).request_delivery_retry(previous.pk)
    third = previous
    assert third.generation == 3
    claimed = OutboxService().claim_delivery(third.pk) if after_claim else None
    MessageDeliveryService().process_resend_event(
        external_event_id="late-original",
        event_type="email.delivered",
        provider_message_id="original-delivered",
        message_log_id=str(original.pk),
        occurred_at=timezone.now(),
    )
    with patch("notifications.channels.email.EmailChannel.send") as send:
        if after_claim:
            with patch.object(OutboxService, "claim_delivery", return_value=claimed):
                OutboxService().dispatch(third.pk)
        else:
            OutboxService().dispatch(third.pk)
    send.assert_not_called()
    third.refresh_from_db()
    assert third.reason_code == "previous_delivery_succeeded"


def test_provider_failure_after_sent_can_be_reprocessed(user, school):
    delivery, _, _ = delivery_for(user)
    with patch("notifications.channels.email.EmailChannel.send", return_value=success()):
        OutboxService().dispatch(delivery.pk)
    MessageDeliveryService().process_resend_event(
        external_event_id="late-failure",
        event_type="email.failed",
        provider_message_id="provider-1",
        message_log_id=str(delivery.pk),
        occurred_at=timezone.now(),
    )
    delivery.refresh_from_db()
    assert delivery.status == delivery.dispatch_state == "FAILED"
    assert OutboxService(user=user).request_delivery_retry(delivery.pk).generation == 2
