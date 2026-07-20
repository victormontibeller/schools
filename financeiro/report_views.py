"""Views de relatórios financeiros, separadas do fluxo transacional."""

import csv
import datetime as dt

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core.permissions import VIEW, access_policy
from financeiro.forms import ReportFilterForm
from financeiro.selectors import BillingSelector


@login_required
@access_policy("finance_revenue_reports", VIEW)
def revenue_report(request: HttpRequest) -> HttpResponse:
    """Renderiza receita prevista e recebida para o período solicitado."""
    initial = {
        "year": request.GET.get("year", dt.date.today().year),
        "month": request.GET.get("month", ""),
    }
    form = ReportFilterForm(request.GET or None, initial=initial)
    if form.is_valid():
        year = form.cleaned_data["year"]
        month_str = form.cleaned_data["month"]
        month = int(month_str) if month_str else None
    else:
        year = dt.date.today().year
        month = None
    selector = BillingSelector(user=request.user)
    competence = selector.competence_report(year=year, month=month)
    cash = selector.cash_report(year=year, month=month)
    return render(
        request,
        "financeiro/revenue_report.html",
        {
            "form": form,
            "competence": competence,
            "cash": cash,
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": "finance_dashboard"},
                {"label": "Relatorio de Receita", "url": None},
            ],
        },
    )


@login_required
@access_policy("finance_overdue_reports", VIEW)
def overdue_report(request: HttpRequest) -> HttpResponse:
    """Renderiza a inadimplência agrupada por faixa de atraso."""
    selector = BillingSelector(user=request.user)
    bands = selector.inadimplencia_por_faixa()
    details = selector.overdue_details()
    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="inadimplencia.csv"'
        writer = csv.writer(response)
        writer.writerow(["Faixa", "Aluno", "Turma", "Contrato", "Títulos", "Mais antigo", "Saldo"])
        for row in details:
            writer.writerow(
                [
                    row["aging_band"],
                    f"{row['student__first_name']} {row['student__last_name']}",
                    row["contract__class_obj__name"] or "",
                    row["contract__name"] or "Avulsa",
                    row["quantity"],
                    row["oldest_due"].isoformat(),
                    row["total"],
                ]
            )
        return response
    return render(
        request,
        "financeiro/overdue_report.html",
        {
            "bands": bands,
            "details": details,
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": "finance_dashboard"},
                {"label": "Inadimplencia", "url": None},
            ],
        },
    )
