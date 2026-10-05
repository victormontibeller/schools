"""Views de relatórios financeiros, separadas do fluxo transacional."""

import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.utils import timezone

from base.context import active_tenant_schema
from base.listing import build_querystring
from base.parsers import parse_optional_int
from core.permissions import VIEW, access_policy
from financeiro.forms import ReportFilterForm
from financeiro.selectors import BillingSelector


@login_required
@access_policy("finance_revenue_reports", VIEW)
def revenue_report(request: HttpRequest) -> HttpResponse:
    """Renderiza receita prevista e recebida para o período solicitado."""
    initial = {
        "year": request.GET.get("year", timezone.localdate().year),
        "month": request.GET.get("month", ""),
    }
    form = ReportFilterForm(request.GET or None, initial=initial)
    if form.is_valid():
        year = form.cleaned_data["year"]
        month_str = form.cleaned_data["month"]
        month = int(month_str) if month_str else None
    else:
        year = timezone.localdate().year
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
    if request.GET.get("format") == "csv":
        rows = selector.iter_overdue_details(
            tenant_schema=active_tenant_schema(), reference_date=timezone.localdate()
        )
        response = StreamingHttpResponse(_overdue_csv(rows), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="inadimplencia.csv"'
        return response
    result = selector.overdue_details(
        page=(parse_optional_int(request.GET.get("page")) or 1),
        page_size=(parse_optional_int(request.GET.get("page_size")) or 20),
    )
    context = {
        "bands": selector.inadimplencia_por_faixa(),
        "result": result,
        "list_query": build_querystring(
            {key: value for key, value in request.GET.items() if key not in {"page", "format"}}
        ),
        "pagination_target": "#overdue-details",
        "pagination_swap": "outerHTML",
        "pagination_push_url": True,
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Financeiro", "url": "finance_dashboard"},
            {"label": "Inadimplência", "url": None},
        ],
    }
    template = (
        "financeiro/partials/overdue_details.html"
        if request.headers.get("HX-Request")
        else "financeiro/overdue_report.html"
    )
    return render(request, template, context)


class _CsvBuffer:
    def write(self, value):
        return value


def _overdue_csv(rows):
    writer = csv.writer(_CsvBuffer())
    yield writer.writerow(
        ["Faixa", "Aluno", "Turma", "Contrato", "Títulos", "Mais antigo", "Saldo"]
    )
    for row in rows:
        yield writer.writerow(
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
