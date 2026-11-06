"""Painel de entregas e reprocessamento humano por domínio autorizado."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from base.exceptions import BusinessRuleViolationError
from base.listing import build_querystring, resolve_listing_state
from core.permissions import access_policy
from notifications.delivery_selectors import CommunicationDeliverySelector
from notifications.outbox_services import OutboxService


@login_required
@access_policy("communication_delivery", "view")
def communication_delivery_list(request):
    state = resolve_listing_state(
        request,
        scope="communication_deliveries",
        allowed_sorts={"created_at"},
        default_sort="created_at",
    )
    context = {
        "result": CommunicationDeliverySelector().list_for_user(
            request.user, state["page"], state["q"]
        ),
        "q": state["q"],
        "list_query": build_querystring({"q": state["q"]}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Entregas", "url": None},
        ],
    }
    template = (
        "notifications/partials/deliveries_table.html"
        if request.headers.get("HX-Request")
        else "notifications/delivery_list.html"
    )
    return render(request, template, context)


@login_required
@require_POST
@access_policy("communication_delivery", "edit")
def communication_delivery_retry(request, pk):
    try:
        OutboxService(user=request.user).request_delivery_retry(pk)
    except BusinessRuleViolationError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(
            request, "Novo envio registrado. A tentativa anterior permanece no histórico."
        )
    return redirect("communication_delivery_list")
