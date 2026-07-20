"""Testes do rastreamento de entrega e webhook assinado da Resend."""

import base64
import datetime as dt
import json
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from svix.webhooks import Webhook

from notifications.channels import ChannelResult
from notifications.delivery_services import MessageDeliveryService
from notifications.models import MessageLog, WebhookEventReceipt

WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"resend-test-secret-32-bytes-value").decode()


class _RetryChannel:
    """Canal determinístico para validar retry sem rede."""

    channel_name = "EMAIL"

    def __init__(self, *, success: bool):
        self.success = success

    def send(self, recipient_address, subject, body, **meta):
        """Retorna falha transitória ou sucesso usando o mesmo log."""
        return ChannelResult(
            success=self.success,
            channel=self.channel_name,
            recipient_address=recipient_address,
            provider_message_id="provider-retry-id" if self.success else "",
            error_message="temporary" if not self.success else "",
            retryable=not self.success,
        )


def _signed_headers(payload: str, event_id: str, timestamp: dt.datetime) -> dict:
    """Monta os cabeçalhos Svix usando o mesmo corpo enviado ao Django."""
    signature = Webhook(WEBHOOK_SECRET).sign(event_id, timestamp, payload)
    return {
        "HTTP_SVIX_ID": event_id,
        "HTTP_SVIX_TIMESTAMP": str(int(timestamp.timestamp())),
        "HTTP_SVIX_SIGNATURE": signature,
    }


def _event_payload(message_log, event_type: str, occurred_at: dt.datetime) -> str:
    """Cria um evento mínimo sem endereço ou conteúdo da mensagem."""
    return json.dumps(
        {
            "type": event_type,
            "created_at": occurred_at.isoformat(),
            "data": {
                "email_id": "provider-email-id",
                "tags": {
                    "tenant_schema": "demo",
                    "message_log_id": str(message_log.pk),
                },
            },
        },
        separators=(",", ":"),
    )


@pytest.mark.django_db
@override_settings(
    ALLOWED_HOSTS=["platform.localhost"],
    RESEND_WEBHOOK_SECRET=WEBHOOK_SECRET,
)
def test_webhook_records_delivery_and_ignores_duplicate(client, user):
    from tenancy.models import School

    School.objects.create(schema_name="demo", name="Demo", created_by=user, updated_by=user)
    message_log = MessageDeliveryService(user=user).create_pending(
        recipient=user,
        channel=MessageLog.Channel.EMAIL,
        recipient_address=user.email,
    )
    occurred_at = timezone.now()
    payload = _event_payload(message_log, "email.delivered", occurred_at)
    headers = _signed_headers(payload, "evt-delivered", occurred_at)

    first = client.post(
        reverse("resend_email_webhook"),
        data=payload,
        content_type="application/json",
        HTTP_HOST="platform.localhost",
        **headers,
    )
    second = client.post(
        reverse("resend_email_webhook"),
        data=payload,
        content_type="application/json",
        HTTP_HOST="platform.localhost",
        **headers,
    )

    message_log.refresh_from_db()
    assert first.status_code == 200
    assert second.status_code == 200
    assert message_log.status == MessageLog.Status.DELIVERED
    assert message_log.delivered_at is not None
    assert WebhookEventReceipt.objects.count() == 1


@pytest.mark.django_db
@override_settings(
    ALLOWED_HOSTS=["platform.localhost"],
    RESEND_WEBHOOK_SECRET=WEBHOOK_SECRET,
)
def test_webhook_does_not_regress_terminal_status(client, user):
    from tenancy.models import School

    School.objects.create(schema_name="demo", name="Demo", created_by=user, updated_by=user)
    message_log = MessageDeliveryService(user=user).create_pending(
        recipient=user,
        channel=MessageLog.Channel.EMAIL,
        recipient_address=user.email,
    )
    delivered_at = timezone.now()
    for event_id, event_type, occurred_at in (
        ("evt-final", "email.delivered", delivered_at),
        ("evt-old", "email.delivery_delayed", delivered_at - dt.timedelta(minutes=5)),
    ):
        payload = _event_payload(message_log, event_type, occurred_at)
        response = client.post(
            reverse("resend_email_webhook"),
            data=payload,
            content_type="application/json",
            HTTP_HOST="platform.localhost",
            **_signed_headers(payload, event_id, timezone.now()),
        )
        assert response.status_code == 200

    message_log.refresh_from_db()
    assert message_log.status == MessageLog.Status.DELIVERED
    assert message_log.last_event == "email.delivered"


@pytest.mark.django_db
def test_system_webhook_command_rolls_back_when_audit_fails(user):
    message_log = MessageDeliveryService(user=user).create_pending(
        recipient=user,
        channel=MessageLog.Channel.EMAIL,
        recipient_address=user.email,
    )
    occurred_at = timezone.now()

    with patch("audit.services.AuditService.record", side_effect=RuntimeError("audit down")):
        with pytest.raises(RuntimeError, match="audit down"):
            MessageDeliveryService(user=None).process_resend_event(
                external_event_id="evt-rollback",
                event_type="email.delivered",
                provider_message_id="provider-rollback",
                message_log_id=str(message_log.pk),
                occurred_at=occurred_at,
            )

    message_log.refresh_from_db()
    assert message_log.status == MessageLog.Status.PENDING
    assert not WebhookEventReceipt.objects.filter(external_event_id="evt-rollback").exists()


@pytest.mark.django_db
@override_settings(
    ALLOWED_HOSTS=["platform.localhost"],
    RESEND_WEBHOOK_SECRET=WEBHOOK_SECRET,
)
def test_webhook_rejects_invalid_signature(client):
    response = client.post(
        reverse("resend_email_webhook"),
        data="{}",
        content_type="application/json",
        HTTP_HOST="platform.localhost",
        HTTP_SVIX_ID="evt-invalid",
        HTTP_SVIX_TIMESTAMP="1",
        HTTP_SVIX_SIGNATURE="v1,invalid",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_transport_retry_reuses_message_log_and_idempotency_key(user):
    from types import SimpleNamespace

    from notifications.transport import MessageTransport

    template = SimpleNamespace(subject="Aviso", body="Conteúdo genérico")
    first = MessageTransport(_RetryChannel(success=False))
    assert first.send_individual(user, template) == 0

    second = MessageTransport(_RetryChannel(success=True))
    assert second.send_individual(user, template, message_log_id=first.last_log_id) == 1

    assert MessageLog.objects.count() == 1
    message_log = MessageLog.objects.get()
    assert message_log.status == MessageLog.Status.SENT
    assert message_log.provider_message_id == "provider-retry-id"
