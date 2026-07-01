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
    from notifications.services import NotificationService

    qs = student.guardians.filter(is_primary=True).select_related("guardian__user")
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


def _notify_class_students(
    class_obj,
    user,
    title: str,
    message: str,
    notif_type: str,
    source: str,
    action_url_prefix: str,
    correlation_id: str,
) -> None:
    """Envia notificacao para alunos ativos de uma turma."""
    from classes.models import Enrollment
    from notifications.services import NotificationService

    student_user_ids = Enrollment.objects.filter(
        class_obj=class_obj, status=Enrollment.Status.ACTIVE
    ).values_list("student__user_id", flat=True)

    for user_id in student_user_ids:
        if user_id is None:
            continue
        NotificationService(user=user).create_notification(
            {
                "recipient_id": user_id,
                "title": title,
                "message": message,
                "type": notif_type,
                "source": source,
                "action_url": action_url_prefix,
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


def _handle_activity_created(event: DomainEvent) -> None:
    activity = event.instance
    _notify_class_students(
        activity.class_obj,
        event.user,
        title="Nova Atividade",
        message=f"Nova atividade em {activity.subject.name}: {activity.title}.",
        notif_type="INFO",
        source="activities",
        action_url_prefix=f"/activities/{activity.pk}/",
        correlation_id=event.correlation_id,
    )


def _handle_calendar_event_created(event: DomainEvent) -> None:
    cal_event = event.instance
    audience = getattr(cal_event, "audience", "ALL")
    title = f"Novo evento: {cal_event.title}"
    msg = cal_event.description or f"Evento em {cal_event.start_date}."

    if audience == "ALL":
        from django.db import connection

        from notifications.tasks import notify_audience_all_task

        notify_audience_all_task.delay(
            connection.schema_name,
            title=title,
            message=msg,
            correlation_id=event.correlation_id,
        )
    elif audience == "CLASS" and cal_event.class_obj:
        _notify_class_students(
            cal_event.class_obj,
            event.user,
            title=title,
            message=msg,
            notif_type="INFO",
            source="calendar",
            action_url_prefix=f"/calendar/{cal_event.pk}/",
            correlation_id=event.correlation_id,
        )


# ── Registro ─────────────────────────────────────────────────────────────────


_SPECIFIC_HANDLERS = {
    ("Student", "INSERT"): _handle_student_created,
    ("Student", "ALERT"): _handle_attendance_threshold,
    ("Student", "CRITICAL"): _handle_attendance_threshold,
    ("Activity", "INSERT"): _handle_activity_created,
    ("CalendarEvent", "INSERT"): _handle_calendar_event_created,
}


def register_event_handlers() -> None:
    """Registra handlers no dispatcher global. Idempotente."""
    global _HANDLERS_REGISTERED
    if _HANDLERS_REGISTERED:
        return
    dispatcher.register(DomainEvent, _on_domain_event)
    _HANDLERS_REGISTERED = True
    logger.info("Handlers de notificacao registrados no dispatcher global.")
