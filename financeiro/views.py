"""Orquestração HTTP do dashboard financeiro."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core.permissions import VIEW, access_policy, role_name
from financeiro.selectors import BillingSelector


@login_required
@access_policy("finance_overview", VIEW)
def finance_dashboard(request: HttpRequest) -> HttpResponse:
    """Exibe KPIs e atalhos autorizados da visão financeira."""
    return render(
        request,
        "financeiro/dashboard.html",
        {
            "kpis": BillingSelector(user=request.user).finance_kpis(),
            "guardian_view": role_name(request.user) == "GUARDIAN",
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": None},
            ],
        },
    )
