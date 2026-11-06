"""Sinais de processamento e recuperação periódica independente do broker original."""

import logging

from celery import shared_task
from django.utils import timezone

from base.context import tenant_schema_context
from base.exceptions import BusinessRuleViolationError, PermissionDeniedError

logger = logging.getLogger(__name__)


def _log_recovery_failure(event: str, schema: str, exc: Exception, **identifiers: str) -> None:
    """Registra a falha isolada sem texto da exceção nem payload da comunicação."""
    logger.error(
        event,
        extra={"tenant_schema": schema, "exception_type": type(exc).__name__, **identifiers},
    )


@shared_task(name="notifications.deliver_outbox")
def deliver_outbox_task(tenant_schema, delivery_id):
    with tenant_schema_context(tenant_schema):
        from notifications.outbox_services import OutboxService

        OutboxService().dispatch(delivery_id)


@shared_task(name="notifications.recover_communications")
def recover_communications_task() -> None:
    """Recupera cada escola sem propagar sua falha para as demais."""
    from tenancy.selectors import SchoolSelector

    for schema in SchoolSelector().list_active_schemas():
        try:
            with tenant_schema_context(schema):
                recover_tenant_communications(schema)
        except Exception as exc:
            _log_recovery_failure("communications_recovery_failed", schema, exc)


def recover_tenant_communications(schema: str) -> None:
    """Coordena intenções independentes, preservando a retentativa dos services."""
    from notifications.announcement_services import AnnouncementService
    from notifications.models import Announcement
    from notifications.outbox_selectors import OutboxSelector
    from notifications.outbox_services import OutboxService

    for announcement in Announcement.objects.filter(
        status="SCHEDULED", scheduled_at__lte=timezone.now()
    ).select_related("author__role")[:100]:
        try:
            AnnouncementService(user=announcement.author).publish_announcement(
                announcement.pk, version=announcement.version
            )
        except (BusinessRuleViolationError, PermissionDeniedError):
            logger.warning(
                "announcement_schedule_blocked",
                extra={"announcement_id": str(announcement.pk), "tenant_schema": schema},
            )
        except Exception as exc:
            _log_recovery_failure(
                "announcement_recovery_failed", schema, exc, announcement_id=str(announcement.pk)
            )
    # Executar diretamente também recupera a indisponibilidade do broker depois que Beat voltou.
    for delivery_id in list(OutboxSelector.pending_ids()):
        try:
            OutboxService().dispatch(delivery_id)
        except Exception as exc:
            _log_recovery_failure(
                "outbox_recovery_failed", schema, exc, delivery_id=str(delivery_id)
            )

    from service_requests.event_services import RequestEventService
    from service_requests.selectors import ServiceRequestSelector

    for request_id in ServiceRequestSelector.overdue_ids():
        try:
            RequestEventService().notify_overdue_request(request_id)
        except Exception as exc:
            _log_recovery_failure(
                "request_recovery_failed", schema, exc, request_id=str(request_id)
            )
