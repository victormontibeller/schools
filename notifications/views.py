"""Views do modulo de notificacoes."""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
from notifications.selectors import AnnouncementSelector, NotificationSelector

logger = logging.getLogger(__name__)


@login_required
def notification_list(request) -> HttpResponse:
    """Lista as notificacoes do usuario logado."""
    unread_count = NotificationSelector().get_unread_for_user(request.user.pk).count()
    notifications = NotificationSelector().get_all_for_user(request.user.pk)[:50]
    return render(
        request,
        "notifications/list.html",
        {"notifications": notifications, "unread_count": unread_count},
    )


@login_required
def notification_mark_read(request, pk) -> HttpResponse:
    """Marca uma notificacao como lida e redireciona para a lista."""
    notification = NotificationSelector().get_by_id(pk)
    from notifications.services import NotificationService

    try:
        NotificationService(user=request.user).mark_as_read(notification.pk)
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        logger.warning("Erro ao marcar notificacao: %s", exc, extra={"pk": str(pk)})
        messages.error(request, str(exc))
    return redirect("notification_list")


@login_required
def notification_mark_all_read(request) -> HttpResponse:
    """Marca todas as notificacoes como lidas."""
    from notifications.services import NotificationService

    NotificationService(user=request.user).mark_all_as_read(request.user.pk)
    return redirect("notification_list")


@login_required
def unread_count(request) -> HttpResponse:
    """Retorna contador de nao lidas (para HTMX polling)."""
    count = NotificationSelector().get_unread_for_user(request.user.pk).count()
    return HttpResponse(str(count) if count else "")


@login_required
def announcement_list(request) -> HttpResponse:
    """Lista comunicados enviados."""
    announcements = AnnouncementSelector().get_sent()[:30]
    return render(
        request,
        "notifications/announcement_list.html",
        {"announcements": announcements},
    )
