"""Handlers de eventos cross-modulo que criam notificacoes automaticamente."""

from __future__ import annotations

import logging

from base.events import DomainEvent, dispatcher

logger = logging.getLogger(__name__)

_HANDLERS_REGISTERED = False


# ── Helpers de notificacao DRY ───────────────────────────────────────────────


def _notify_guardians(
    student,
    user,
    title: str,
    message: str,
    notif_type: str,
    source: str,
    action_url: str,
    correlation_id: str,
) -> None:
    """Envia notificacao para responsaveis principais de um aluno."""
    from guardians.selectors import GuardianSelector
    from notifications.services import NotificationService

    qs = GuardianSelector().custodial_links_for_students([student.pk]).filter(is_primary=True)
    for link in qs:
        guardian_user = link.guardian.user
        if guardian_user is None:
            continue
        NotificationService(user=user).create_notification(
            {
                "recipient_id": guardian_user.pk,
                "title": title,
                "message": message,
                "type": notif_type,
                "source": source,
                "action_url": action_url,
                "correlation_id": correlation_id,
            }
        )


# ── Roteador generico ────────────────────────────────────────────────────────


def _on_domain_event(event: DomainEvent) -> None:
    """Roteia DomainEvent para o handler especifico via tabela (model, operation)."""
    if event.instance is None:
        return

    model_name = type(event.instance).__name__
    operation = event.operation

    handler = _SPECIFIC_HANDLERS.get((model_name, operation))
    if handler is not None:
        handler(event)


# ── Handlers especificos ─────────────────────────────────────────────────────


def _handle_student_created(event: DomainEvent) -> None:
    student = event.instance
    _notify_guardians(
        student,
        event.user,
        title="Novo aluno vinculado",
        message=f"{student.get_full_name()} foi vinculado(a) a voce como responsavel.",
        notif_type="SUCCESS",
        source="students",
        action_url=f"/students/{student.pk}/",
        correlation_id=event.correlation_id,
    )


def _handle_attendance_threshold(event: DomainEvent) -> None:
    student = event.instance
    thresholds = {
        "ALERT": ("Alerta de Frequencia", "75%", "ALERT"),
        "CRITICAL": ("Frequencia Critica", "50%", "CRITICAL"),
    }
    config = thresholds.get(event.operation)
    if config is None:
        return
    title, pct, notif_type = config
    _notify_guardians(
        student,
        event.user,
        title=title,
        message=f"{student.get_full_name()} esta com frequencia abaixo de {pct}.",
        notif_type=notif_type,
        source="attendance",
        action_url=f"/students/{student.pk}/attendance/",
        correlation_id=event.correlation_id,
    )


def _handle_pilot_communication(event: DomainEvent) -> None:
    from notifications.domain_event_services import DomainCommunicationService

    instance = event.instance
    name = type(instance).__name__
    if (name, event.operation) not in _REQUIRED_EVENTS:
        return
    old = event.old_values or {}
    kind = None
    if name == "Activity" and event.operation == "INSERT":
        kind = "activity_published"
    elif name == "CalendarEvent" and (
        event.operation == "INSERT" or (not old.get("is_public") and instance.is_public)
    ):
        kind = "calendar_published"
    elif name == "PaymentRecord" and old.get("status") != instance.status:
        kind = {"CONFIRMED": "payment_confirmed", "REVERSED": "payment_reversed"}.get(
            instance.status
        )
    elif name == "EnrollmentApplication" and old.get("status") != instance.status:
        kind = {"ENROLLED": "enrollment_confirmed", "CORRECTION_REQUIRED": "document_action"}.get(
            instance.status
        )
    if kind:
        DomainCommunicationService(user=event.user).emit_domain_event(instance, kind)


# ── Registro ─────────────────────────────────────────────────────────────────


_SPECIFIC_HANDLERS = {
    ("Student", "INSERT"): _handle_student_created,
    ("Student", "ALERT"): _handle_attendance_threshold,
    ("Student", "CRITICAL"): _handle_attendance_threshold,
}


_REQUIRED_EVENTS = {
    ("Activity", "INSERT"),
    ("CalendarEvent", "INSERT"),
    ("CalendarEvent", "UPDATE"),
    ("PaymentRecord", "UPDATE"),
    ("EnrollmentApplication", "UPDATE"),
}


def register_event_handlers() -> None:
    """Registra handlers no dispatcher global. Idempotente."""
    global _HANDLERS_REGISTERED
    if _HANDLERS_REGISTERED:
        return
    dispatcher.register(DomainEvent, _handle_pilot_communication, required=True)
    dispatcher.register(DomainEvent, _on_domain_event)
    _HANDLERS_REGISTERED = True
    logger.info("Handlers de notificacao registrados no dispatcher global.")
