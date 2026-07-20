"""Serviços de persistência e reconciliação de entregas por provedores externos."""

from __future__ import annotations

from django.utils import timezone

from base.exceptions import ObjectNotFoundError
from base.services import BaseService, system_command


class MessageDeliveryService(BaseService):
    """Mantém o ciclo de vida auditável de uma tentativa de entrega."""

    def create_pending(
        self,
        *,
        recipient,
        channel: str,
        recipient_address: str,
        announcement=None,
        diary_publication=None,
        diary_publication_id=None,
    ):
        """Cria o registro antes de qualquer chamada de rede."""
        from notifications.contracts import MessageLog

        message_log = MessageLog.objects.create(
            announcement=announcement,
            diary_publication=diary_publication,
            diary_publication_id=diary_publication_id,
            recipient=recipient,
            channel=channel,
            recipient_address=recipient_address,
            status=MessageLog.Status.PENDING,
            provider="RESEND" if channel == MessageLog.Channel.EMAIL else "",
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", message_log)
        self._log(
            "message_delivery_pending",
            message_log_id=str(message_log.pk),
            channel=channel,
        )
        return message_log

    def get_pending(self, message_log_id):
        """Recupera uma tentativa existente para retry idempotente."""
        from notifications.contracts import MessageLog

        try:
            return MessageLog.objects.get(pk=message_log_id, status=MessageLog.Status.PENDING)
        except MessageLog.DoesNotExist:
            raise ObjectNotFoundError("MessageLog", str(message_log_id)) from None

    def record_channel_result(self, message_log_id, result):
        """Atualiza o log sem regredir um webhook já processado."""
        from notifications.contracts import MessageLog

        try:
            message_log = MessageLog.objects.get(pk=message_log_id)
        except MessageLog.DoesNotExist:
            raise ObjectNotFoundError("MessageLog", str(message_log_id)) from None
        old = self._snapshot(
            message_log,
            ["status", "provider_message_id", "error_message", "sent_at"],
        )
        if result.provider_message_id and not message_log.provider_message_id:
            message_log.provider_message_id = result.provider_message_id
        if result.success:
            if message_log.status == MessageLog.Status.PENDING:
                message_log.status = MessageLog.Status.SENT
            message_log.sent_at = message_log.sent_at or timezone.now()
            message_log.error_message = ""
        else:
            message_log.error_message = result.error_message
            if not result.retryable:
                message_log.status = MessageLog.Status.FAILED
        message_log.updated_by = self.user
        message_log.save()
        self._record_audit("UPDATE", message_log, old_values=old)
        self._log(
            "message_delivery_result",
            message_log_id=str(message_log.pk),
            channel=message_log.channel,
            status=message_log.status,
            retryable=result.retryable,
        )
        return message_log

    @system_command
    def process_resend_event(
        self,
        *,
        external_event_id: str,
        event_type: str,
        provider_message_id: str,
        message_log_id: str,
        occurred_at,
    ) -> bool:
        """Aplica um evento Resend assinado de forma idempotente e monotônica."""
        from notifications.contracts import MessageLog, WebhookEventReceipt

        if WebhookEventReceipt.objects.filter(external_event_id=external_event_id).exists():
            return False
        try:
            message_log = MessageLog.objects.select_for_update().get(
                pk=message_log_id,
                channel=MessageLog.Channel.EMAIL,
            )
        except MessageLog.DoesNotExist:
            raise ObjectNotFoundError("MessageLog", str(message_log_id)) from None
        if message_log.provider_message_id not in {None, "", provider_message_id}:
            raise ObjectNotFoundError("MessageLog", str(message_log_id))

        receipt = WebhookEventReceipt.objects.create(
            provider="RESEND",
            external_event_id=external_event_id,
            event_type=event_type,
            provider_message_id=provider_message_id,
            occurred_at=occurred_at,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", receipt)

        old = self._snapshot(
            message_log,
            [
                "status",
                "provider_message_id",
                "last_event",
                "event_occurred_at",
                "sent_at",
                "delivered_at",
            ],
        )
        message_log.provider_message_id = provider_message_id
        if self._event_can_update(message_log, event_type, occurred_at):
            message_log.status = self._status_for_event(event_type)
            message_log.last_event = event_type
            message_log.event_occurred_at = occurred_at
            if event_type == "email.sent":
                message_log.sent_at = message_log.sent_at or occurred_at
            if event_type == "email.delivered":
                message_log.delivered_at = occurred_at
        message_log.updated_by = self.user
        message_log.save()
        self._record_audit("UPDATE", message_log, old_values=old)
        self._log(
            "resend_webhook_processed",
            message_log_id=str(message_log.pk),
            event_type=event_type,
        )
        return True

    @staticmethod
    def _status_for_event(event_type: str) -> str:
        """Mapeia eventos aceitos para estados persistidos."""
        from notifications.contracts import MessageLog

        return {
            "email.sent": MessageLog.Status.SENT,
            "email.delivered": MessageLog.Status.DELIVERED,
            "email.delivery_delayed": MessageLog.Status.DELAYED,
            "email.bounced": MessageLog.Status.BOUNCED,
            "email.suppressed": MessageLog.Status.SUPPRESSED,
            "email.complained": MessageLog.Status.COMPLAINED,
            "email.failed": MessageLog.Status.FAILED,
        }[event_type]

    @classmethod
    def _event_can_update(cls, message_log, event_type: str, occurred_at) -> bool:
        """Evita que eventos antigos ou intermediários regressem um estado final."""
        from notifications.contracts import MessageLog

        terminal = {
            MessageLog.Status.DELIVERED,
            MessageLog.Status.BOUNCED,
            MessageLog.Status.SUPPRESSED,
            MessageLog.Status.COMPLAINED,
            MessageLog.Status.FAILED,
        }
        next_status = cls._status_for_event(event_type)
        if message_log.status in terminal and next_status not in terminal:
            return False
        if message_log.event_occurred_at and occurred_at < message_log.event_occurred_at:
            return False
        return True
