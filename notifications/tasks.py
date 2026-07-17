"""Tarefas Celery para envio assincrono de notificacoes e comunicados.

As tasks sao wrappers finos que delegam para MessageTransport + canal SDK.
Toda a logica de renderizacao, envio, log e retry fica no transport.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

from base.context import tenant_schema_context
from notifications.task_helpers import get_transport, retry_email_if_needed

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_diary_email_task(
    self,
    tenant_schema: str,
    user_id: str,
    event: str,
    action_url: str,
    publication_id: str | None = None,
    message_log_id: str | None = None,
) -> None:
    """Envia um evento genérico da Agenda sem incluir conteúdo ou nome do aluno."""
    with tenant_schema_context(tenant_schema):
        from core.contracts import CustomUser

        user = CustomUser.objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            return
        if event == "publication":
            try:
                guardian = user.guardian_profile
            except ObjectDoesNotExist:
                return
            if not guardian.accepts_email_notifications:
                return
        content = {
            "publication": (
                "Agenda escolar disponível",
                "A escola publicou uma atualização da agenda. Acesse: {{ action_url }}",
            ),
            "review_requested": (
                "Agenda aguardando revisão",
                "Uma agenda foi enviada para revisão. Acesse: {{ action_url }}",
            ),
            "changes_requested": (
                "Correção solicitada na Agenda",
                "Uma agenda foi devolvida para correção. Acesse: {{ action_url }}",
            ),
        }.get(event)
        if content is None:
            return
        transport = get_transport("EMAIL")
        result = transport.send_individual(
            user,
            SimpleNamespace(subject=content[0], body=content[1]),
            {"action_url": action_url},
            message_log_id=message_log_id,
            diary_publication_id=publication_id,
            category=f"student_diary_{event}",
        )
        retry_email_if_needed(self, transport, result)


# ── Envio em lote para comunicado ────────────────────────────────────────────


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_announcement_email_task(self, tenant_schema: str, announcement_id):
    """Envia comunicado por e-mail em lote para a audiencia."""
    with tenant_schema_context(tenant_schema):
        from notifications.contracts import Announcement

        announcement = _fetch_or_log(Announcement, announcement_id, "Comunicado")
        if announcement is None:
            return

        transport = get_transport("EMAIL")
        success, failed = transport.send_announcement_batch(announcement)
        if failed > 0 and success == 0:
            raise self.retry()


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_announcement_whatsapp_task(self, tenant_schema: str, announcement_id):
    """Envia comunicado por WhatsApp em lote (stub)."""
    with tenant_schema_context(tenant_schema):
        from notifications.contracts import Announcement

        announcement = _fetch_or_log(Announcement, announcement_id, "Comunicado")
        if announcement is None:
            return

        transport = get_transport("WHATSAPP")
        transport.send_announcement_batch(announcement)


# ── Notificacao em lote para audiencia ALL ───────────────────────────────────


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def notify_audience_all_task(
    self, tenant_schema: str, title: str, message: str, correlation_id: str = ""
):
    """Cria notificacoes in-app em lote para todos os usuarios ativos do tenant."""
    with tenant_schema_context(tenant_schema):
        from core.contracts import CustomUser
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
