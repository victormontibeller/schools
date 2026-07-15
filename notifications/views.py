"""Views do modulo de notificacoes."""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
from base.listing import build_querystring, build_sorting, resolve_listing_state
from notifications.selectors import AnnouncementSelector, NotificationSelector

logger = logging.getLogger(__name__)
ANNOUNCEMENT_SORTS = {
    "title": "title",
    "-title": "-title",
    "sent_at": "sent_at",
    "-sent_at": "-sent_at",
    "audience": "audience",
    "-audience": "-audience",
}


@login_required
def notification_list(request) -> HttpResponse:
    """Lista as notificacoes do usuario logado."""
    if request.headers.get("HX-Request") and request.GET.get("context") == "header":
        return _render_header_notifications(request)

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
        logger.warning(
            "Erro ao marcar notificacao",
            extra={"pk": str(pk), "exception_type": type(exc).__name__},
        )
        messages.error(request, str(exc))
    if request.headers.get("HX-Request"):
        return _render_header_notifications(request)
    return redirect("notification_list")


@login_required
def notification_mark_all_read(request) -> HttpResponse:
    """Marca todas as notificacoes como lidas."""
    from notifications.services import NotificationService

    NotificationService(user=request.user).mark_all_as_read(request.user.pk)
    if request.headers.get("HX-Request"):
        return _render_header_notifications(request)
    return redirect("notification_list")


@login_required
def unread_count(request) -> HttpResponse:
    """Retorna contador de nao lidas (para HTMX polling)."""
    count = NotificationSelector().get_unread_for_user(request.user.pk).count()
    return HttpResponse(str(count) if count else "")


def _render_header_notifications(request) -> HttpResponse:
    """Renderiza o popup de notificacoes do cabecalho."""
    unread_count = NotificationSelector().get_unread_for_user(request.user.pk).count()
    notifications = NotificationSelector().get_all_for_user(request.user.pk)[:8]
    return render(
        request,
        "notifications/partials/header_notifications.html",
        {"notifications": notifications, "unread_count": unread_count},
    )


@login_required
def announcement_list(request) -> HttpResponse:
    """Lista comunicados enviados."""
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="announcements_list",
        allowed_sorts=set(ANNOUNCEMENT_SORTS),
        default_sort="-sent_at",
    )
    context = {
        "result": AnnouncementSelector().list_sent(
            state["q"], ANNOUNCEMENT_SORTS[state["sort"]], page
        ),
        "q": state["q"],
        "sort": state["sort"],
        "sorting": build_sorting(
            current_sort=state["sort"],
            search=state["q"],
            sortable_fields=["title", "sent_at", "audience"],
        ),
        "list_query": build_querystring({"q": state["q"], "sort": state["sort"]}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Comunicados", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "notifications/partials/announcements_table.html", context)
    return render(request, "notifications/announcement_list.html", context)


@login_required
def announcement_detail(request, pk) -> HttpResponse:
    """Exibe o comunicado selecionado pela listagem."""
    announcement = AnnouncementSelector().get_by_id(pk)
    return render(request, "notifications/announcement_detail.html", {"announcement": announcement})
