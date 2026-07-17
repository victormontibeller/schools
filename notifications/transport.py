"""Orquestrador de templates, canais e rastreabilidade de mensagens."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist
from django.db import connection

from notifications.channels import ChannelResult

if TYPE_CHECKING:
    from notifications.channels.base import BaseChannel

logger = logging.getLogger(__name__)
_VARIABLE_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_template(template_body: str, context: dict) -> str:
    """Renderiza variáveis simples no formato ``{{ nome }}``."""
    return _VARIABLE_RE.sub(
        lambda match: str(context.get(match.group(1), match.group(0))), template_body
    )


class MessageTransport:
    """Coordena o canal externo sem manter transações abertas durante a rede."""

    def __init__(self, channel: BaseChannel):
        self.channel = channel
        self.last_result: ChannelResult | None = None
        self.last_log_id = None

    def send_individual(
        self,
        user,
        template,
        context: dict | None = None,
        *,
        force: bool = False,
        message_log_id=None,
        diary_publication=None,
        diary_publication_id=None,
        category: str = "notification",
    ) -> int:
        """Envia uma mensagem individual e reutiliza o log durante retries."""
        context = context or {}
        if not force and not self._allows_channel(user):
            return 0
        subject = render_template(template.subject, context) if template.subject else ""
        body = render_template(template.body, context)
        address = self._resolve_address(user)
        if not address:
            self._record_pre_send_failure(user, diary_publication=diary_publication)
            return 0

        delivery = self._prepare_delivery(
            user=user,
            address=address,
            message_log_id=message_log_id,
            diary_publication=diary_publication,
            diary_publication_id=diary_publication_id,
        )
        result = self.channel.send(
            recipient_address=delivery.recipient_address,
            subject=subject,
            body=body,
            tenant_schema=getattr(connection, "schema_name", "public"),
            message_log_id=str(delivery.pk),
            idempotency_key=f"message-log/{delivery.pk}",
            category=category,
        )
        self._record_result(delivery.pk, result)
        return 1 if result.success else 0

    def send_announcement_batch(self, announcement) -> tuple[int, int]:
        """Envia comunicado para a audiência respeitando consentimentos."""
        from notifications.services import AnnouncementService

        recipients = AnnouncementService().get_audience_users(
            announcement.audience, announcement.class_obj_id
        )
        success = 0
        failed = 0
        for user in recipients:
            if not self._allows_channel(user):
                continue
            address = self._resolve_address(user)
            if not address:
                self._record_pre_send_failure(user, announcement=announcement)
                failed += 1
                continue
            delivery = self._prepare_delivery(
                user=user,
                address=address,
                announcement=announcement,
            )
            result = self.channel.send(
                recipient_address=delivery.recipient_address,
                subject=announcement.title,
                body=announcement.body,
                tenant_schema=getattr(connection, "schema_name", "public"),
                message_log_id=str(delivery.pk),
                idempotency_key=f"message-log/{delivery.pk}",
                category="announcement",
            )
            self._record_result(delivery.pk, result)
            success += int(result.success)
            failed += int(not result.success)
        logger.info(
            "message_batch_completed",
            extra={
                "channel": self.channel.channel_name,
                "announcement_id": str(announcement.pk),
                "success_count": success,
                "failure_count": failed,
            },
        )
        return success, failed

    def _prepare_delivery(
        self,
        *,
        user,
        address: str,
        message_log_id=None,
        announcement=None,
        diary_publication=None,
        diary_publication_id=None,
    ):
        """Cria ou recupera o log que identifica a chamada externa."""
        from notifications.delivery_services import MessageDeliveryService

        service = MessageDeliveryService(user=None)
        delivery = (
            service.get_pending(message_log_id)
            if message_log_id
            else service.create_pending(
                recipient=user,
                channel=self.channel.channel_name,
                recipient_address=address,
                announcement=announcement,
                diary_publication=diary_publication,
                diary_publication_id=diary_publication_id,
            )
        )
        self.last_log_id = delivery.pk
        return delivery

    def _record_result(self, message_log_id, result: ChannelResult) -> None:
        """Persiste o resultado sanitizado retornado pelo canal."""
        from notifications.delivery_services import MessageDeliveryService

        self.last_result = result
        MessageDeliveryService(user=None).record_channel_result(message_log_id, result)
        level = logging.INFO if result.success else logging.WARNING
        logger.log(
            level,
            "message_channel_result",
            extra={
                "channel": self.channel.channel_name,
                "message_log_id": str(message_log_id),
                "success": result.success,
                "retryable": result.retryable,
                "status_code": result.status_code,
            },
        )

    def _record_pre_send_failure(
        self,
        user,
        *,
        announcement=None,
        diary_publication=None,
    ) -> None:
        """Registra endereço ausente sem realizar chamada externa."""
        delivery = self._prepare_delivery(
            user=user,
            address="",
            announcement=announcement,
            diary_publication=diary_publication,
        )
        result = ChannelResult(
            success=False,
            channel=self.channel.channel_name,
            recipient_address="",
            error_message="recipient_address_missing",
        )
        self._record_result(delivery.pk, result)

    def _resolve_address(self, user) -> str:
        """Retorna o destino correspondente ao canal."""
        if self.channel.channel_name == "EMAIL":
            return getattr(user, "email", "")
        if self.channel.channel_name == "WHATSAPP":
            return getattr(user, "phone", "")
        return ""

    def _allows_channel(self, user) -> bool:
        """Respeita a preferência do perfil quando ela existe."""
        field = (
            "accepts_email_notifications"
            if self.channel.channel_name == "EMAIL"
            else "accepts_whatsapp_notifications"
        )
        for relation in ("teacher_profile", "student_profile", "guardian_profile"):
            try:
                profile = getattr(user, relation)
            except ObjectDoesNotExist:
                continue
            return bool(getattr(profile, field, False))
        return True
