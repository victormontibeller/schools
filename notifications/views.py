"""Views do modulo de notificacoes."""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

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
RESEND_EMAIL_EVENTS = {
    "email.sent",
    "email.delivered",
    "email.delivery_delayed",
    "email.bounced",
    "email.failed",
    "email.suppressed",
    "email.complained",
}


@csrf_exempt
@require_POST
def resend_email_webhook(request) -> HttpResponse:
    """Verifica e processa eventos Resend somente no domínio da plataforma."""
    from django.conf import settings
    from django.utils.dateparse import parse_datetime
    from svix.webhooks import Webhook

    from base.context import tenant_schema_context
    from core.tenant_routing import is_platform_request
    from notifications.delivery_services import MessageDeliveryService
    from tenancy.selectors import SchoolSelector

    if not is_platform_request(request):
        return HttpResponse(status=404)
    if len(request.body) > 262_144:
        return HttpResponse(status=413)
    if not settings.RESEND_WEBHOOK_SECRET:
        logger.error("resend_webhook_secret_missing")
        return HttpResponse(status=503)
    headers = {
        "svix-id": request.headers.get("svix-id", ""),
        "svix-timestamp": request.headers.get("svix-timestamp", ""),
        "svix-signature": request.headers.get("svix-signature", ""),
    }
    try:
        event = Webhook(settings.RESEND_WEBHOOK_SECRET).verify(request.body, headers)
    except Exception:
        logger.warning("resend_webhook_signature_invalid")
        return HttpResponse(status=400)

    event_type = str(event.get("type", ""))
    if event_type not in RESEND_EMAIL_EVENTS:
        return HttpResponse(status=200)
    data = event.get("data") or {}
    tags = data.get("tags") or {}
    schema_name = str(tags.get("tenant_schema", ""))
    message_log_id = str(tags.get("message_log_id", ""))
    provider_message_id = str(data.get("email_id", ""))
    occurred_at = parse_datetime(str(event.get("created_at", "")))
    external_event_id = headers["svix-id"]
    if not all([schema_name, message_log_id, provider_message_id, occurred_at, external_event_id]):
        logger.warning("resend_webhook_payload_unmappable")
        return HttpResponse(status=200)
    try:
        school = SchoolSelector().get_active_by_schema(schema_name)
        with tenant_schema_context(school.schema_name):
            MessageDeliveryService(user=None).process_resend_event(
                external_event_id=external_event_id,
                event_type=event_type,
                provider_message_id=provider_message_id,
                message_log_id=message_log_id,
                occurred_at=occurred_at,
            )
    except ObjectNotFoundError:
        logger.warning(
            "resend_webhook_target_not_found",
            extra={"tenant": schema_name, "message_log_id": message_log_id},
        )
    return HttpResponse(status=200)


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
        NotificationService(user=request.user).mark_as_read_for_user(
            notification.pk, request.user.pk
        )
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
