"""MessageTransport: orquestrador generico de envio de mensagens.

Unifica renderizacao de template, envio via canal SDK, criacao de MessageLog
e retry. Usado pelas tasks Celery e handlers de evento.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from notifications.channels import ChannelResult

if TYPE_CHECKING:
    from notifications.channels.base import BaseChannel

logger = logging.getLogger(__name__)

_VARIABLE_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_template(template_body: str, context: dict) -> str:
    """Renderiza template substituindo variaveis {{ nome }} pelos valores do contexto."""
    return _VARIABLE_RE.sub(lambda m: str(context.get(m.group(1), m.group(0))), template_body)


class MessageTransport:
    """Orquestrador de envio de mensagens que abstrai canal, log e template.

    Uso:
        transport = MessageTransport(EmailChannel())
        transport.send_individual(user, template, context={"nome": "Joao"})
        transport.send_announcement_batch(announcement)
    """

    def __init__(self, channel: BaseChannel):
        self.channel: BaseChannel = channel

    # ── Envio individual via template ───────────────────────────────────────

    @transaction.atomic
    def send_individual(self, user, template, context: dict | None = None) -> int:
        """Envia mensagem individual renderizando template para um usuario.

        Args:
            user: instancia de CustomUser (deve ter email e/ou phone).
            template: instancia de MessageTemplate.
            context: dict de variaveis para o template.

        Returns:
            1 se enviado, 0 se falhou.
        """
        context = context or {}
        if not self._allows_channel(user):
            return 0
        subject = render_template(template.subject, context) if template.subject else ""
        body = render_template(template.body, context)

        address = self._resolve_address(user)
        if not address:
            self._log_failure(user=user, error_message="Endereco de destinatario nao encontrado.")
            return 0

        result = self.channel.send(recipient_address=address, subject=subject, body=body)
        self._log_result(result, user=user)
        return 1 if result.success else 0

    # ── Envio em lote para comunicado ───────────────────────────────────────

    @transaction.atomic
    def send_announcement_batch(self, announcement) -> tuple[int, int]:
        """Envia comunicado para todos os destinatarios da audiencia.

        Returns:
            (sucessos, falhas).
        """
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
                self._log_failure(
                    user=user,
                    announcement=announcement,
                    error_message="Endereco de destinatario nao encontrado.",
                )
                failed += 1
                continue

            result = self.channel.send(
                recipient_address=address,
                subject=announcement.title,
                body=announcement.body,
            )
            self._log_result(result, user=user, announcement=announcement)
            if result.success:
                success += 1
            else:
                failed += 1

        logger.info(
            "Lote %s concluido: comunicado=%s sucesso=%d falhas=%d",
            self.channel.channel_name,
            announcement.pk,
            success,
            failed,
        )
        return success, failed

    # ── Helpers internos ────────────────────────────────────────────────────

    def _resolve_address(self, user) -> str:
        """Retorna o endereco de destino conforme o canal."""
        if self.channel.channel_name == "EMAIL":
            return getattr(user, "email", "")
        if self.channel.channel_name == "WHATSAPP":
            return getattr(user, "phone", "")
        return ""

    def _allows_channel(self, user) -> bool:
        """Respeita o consentimento do perfil quando o usuário representa uma pessoa."""
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

    def _log_result(self, result: ChannelResult, user=None, announcement=None) -> None:
        """Cria MessageLog a partir de um ChannelResult."""
        from notifications.models import MessageLog
        from notifications.services import AnnouncementService

        AnnouncementService().log_delivery(
            announcement=announcement,
            recipient=user,
            channel=self.channel.channel_name,
            recipient_address=result.recipient_address,
            status=MessageLog.Status.SENT if result.success else MessageLog.Status.FAILED,
            error_message=result.error_message,
        )
        if result.success:
            logger.debug("Mensagem enviada pelo canal %s", self.channel.channel_name)
        else:
            logger.warning("Falha no envio pelo canal %s", self.channel.channel_name)

    def _log_failure(self, user=None, announcement=None, error_message: str = "") -> None:
        """Cria MessageLog para falha pre-envio (ex: endereco ausente)."""
        from notifications.models import MessageLog
        from notifications.services import AnnouncementService

        AnnouncementService().log_delivery(
            announcement=announcement,
            recipient=user,
            channel=self.channel.channel_name,
            recipient_address="",
            status=MessageLog.Status.FAILED,
            error_message=error_message,
        )
