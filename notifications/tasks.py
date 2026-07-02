"""Tarefas Celery para envio assincrono de notificacoes e comunicados.

As tasks sao wrappers finos que delegam para MessageTransport + canal SDK.
Toda a logica de renderizacao, envio, log e retry fica no transport.
"""

from __future__ import annotations

import logging

from celery import shared_task

from base.context import tenant_schema_context

logger = logging.getLogger(__name__)


def _get_transport(channel_name: str):
    """Factory: retorna MessageTransport para o canal solicitado."""
    from notifications.channels import EmailChannel, WhatsAppChannel
    from notifications.transport import MessageTransport

    channels = {
        "EMAIL": EmailChannel(),
        "WHATSAPP": WhatsAppChannel(),
    }
    return MessageTransport(channels[channel_name])


# ── Envio individual via template ────────────────────────────────────────────


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, tenant_schema: str, user_id, template_id, context: dict | None = None):
    """Envia e-mail individual renderizando template com contexto."""
    with tenant_schema_context(tenant_schema):
        from core.models import CustomUser
        from notifications.models import MessageTemplate

        user = _fetch_or_log(CustomUser, user_id, "Usuario")
        if user is None:
            return
        template = _fetch_or_log(MessageTemplate, template_id, "Template de email")
        if template is None:
            return

        transport = _get_transport("EMAIL")
        result = transport.send_individual(user, template, context)
        if result == 0:
            raise self.retry()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_whatsapp_task(
    self, tenant_schema: str, phone: str, template_id, context: dict | None = None
):
    """Envia WhatsApp individual renderizando template (stub)."""
    with tenant_schema_context(tenant_schema):
        from notifications.models import MessageTemplate

        template = _fetch_or_log(MessageTemplate, template_id, "Template de WhatsApp")
        if template is None:
            return

        transport = _get_transport("WHATSAPP")
        transport.channel.send(recipient_address=phone, subject="", body="")

        # Log via transport mesmo para stub.
        from notifications.models import MessageLog
        from notifications.services import AnnouncementService

        AnnouncementService().log_delivery(
            channel=MessageLog.Channel.WHATSAPP,
            recipient_address=phone,
            status=MessageLog.Status.FAILED,
            error_message="Provedor WhatsApp nao configurado (stub).",
        )


# ── Envio em lote para comunicado ────────────────────────────────────────────


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_announcement_email_task(self, tenant_schema: str, announcement_id):
    """Envia comunicado por e-mail em lote para a audiencia."""
    with tenant_schema_context(tenant_schema):
        from notifications.models import Announcement

        announcement = _fetch_or_log(Announcement, announcement_id, "Comunicado")
        if announcement is None:
            return

        transport = _get_transport("EMAIL")
        success, failed = transport.send_announcement_batch(announcement)
        if failed > 0 and success == 0:
            raise self.retry()


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_announcement_whatsapp_task(self, tenant_schema: str, announcement_id):
    """Envia comunicado por WhatsApp em lote (stub)."""
    with tenant_schema_context(tenant_schema):
        from notifications.models import Announcement

        announcement = _fetch_or_log(Announcement, announcement_id, "Comunicado")
        if announcement is None:
            return

        transport = _get_transport("WHATSAPP")
        transport.send_announcement_batch(announcement)


# ── Notificacao em lote para audiencia ALL ───────────────────────────────────


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def notify_audience_all_task(
    self, tenant_schema: str, title: str, message: str, correlation_id: str = ""
):
    """Cria notificacoes in-app em lote para todos os usuarios ativos do tenant."""
    with tenant_schema_context(tenant_schema):
        from core.models import CustomUser
        from notifications.services import NotificationService

        chunk_size = 500
        total = 0
        user_ids = list(CustomUser.objects.filter(is_active=True).values_list("pk", flat=True))

        for i in range(0, len(user_ids), chunk_size):
            chunk = user_ids[i : i + chunk_size]
            total += NotificationService().create_notifications_bulk(
                chunk,
                {
                    "title": title,
                    "message": message,
                    "source": "calendar",
                    "correlation_id": correlation_id,
                },
            )

        logger.info("Notificacoes em lote: total=%d correlation_id=%s", total, correlation_id)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _fetch_or_log(model, pk, label: str):
    """Busca instancia ou loga warning; retorna None se nao encontrar."""
    try:
        return model.objects.get(pk=pk)
    except model.DoesNotExist:
        logger.warning("%s %s nao encontrado(a).", label, pk)
        return None
