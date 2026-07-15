"""Views de relatórios financeiros, separadas do fluxo transacional."""

import datetime as dt

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from financeiro.forms import ReportFilterForm
from financeiro.selectors import BillingSelector


@login_required
def revenue_report(request: HttpRequest) -> HttpResponse:
    """Renderiza receita prevista e recebida para o período solicitado."""
    initial = {
        "year": request.GET.get("year", dt.date.today().year),
        "month": request.GET.get("month", ""),
    }
    form = ReportFilterForm(initial=initial)
    year = int(initial["year"]) if initial["year"] else dt.date.today().year
    month_str = initial["month"]
    month = int(month_str) if month_str else None
    report = BillingSelector().relatorio_previsto_x_recebido(year=year, month=month)
    return render(
        request,
        "financeiro/revenue_report.html",
        {
            "form": form,
            "report": report,
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": "finance_dashboard"},
                {"label": "Relatorio de Receita", "url": None},
            ],
        },
    )


@login_required
def overdue_report(request: HttpRequest) -> HttpResponse:
    """Renderiza a inadimplência agrupada por faixa de atraso."""
    bands = BillingSelector().inadimplencia_por_faixa()
    return render(
        request,
        "financeiro/overdue_report.html",
        {
            "bands": bands,
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": "finance_dashboard"},
                {"label": "Inadimplencia", "url": None},
            ],
        },
    )
