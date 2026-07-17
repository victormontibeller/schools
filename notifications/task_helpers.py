"""Helpers compartilhados pelas tasks de entrega de notificações."""

from __future__ import annotations

from typing import Any

from notifications.transport import MessageTransport


def get_transport(channel_name: str) -> MessageTransport:
    """Constrói o transporte correspondente ao canal solicitado."""
    from notifications.channels import EmailChannel, WhatsAppChannel

    channels = {
        "EMAIL": EmailChannel(),
        "WHATSAPP": WhatsAppChannel(),
    }
    return MessageTransport(channels[channel_name])


def retry_email_if_needed(task: Any, transport: MessageTransport, result: int) -> None:
    """Repete somente falhas transitórias preservando a identidade da entrega."""
    if (
        result
        or transport.last_result is None
        or not transport.last_result.retryable
        or transport.last_log_id is None
    ):
        return
    if task.request.retries >= task.max_retries:
        from notifications.channels import ChannelResult
        from notifications.delivery_services import MessageDeliveryService

        MessageDeliveryService(user=None).record_channel_result(
            transport.last_log_id,
            ChannelResult(
                success=False,
                channel="EMAIL",
                recipient_address="",
                error_message="retry_exhausted",
            ),
        )
        return
    retry_kwargs = dict(task.request.kwargs or {})
    retry_kwargs["message_log_id"] = str(transport.last_log_id)
    raise task.retry(kwargs=retry_kwargs)
