"""Views HTMX do modulo Financeiro Escolar — secretaria/financeiro."""

import datetime as dt
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.listing import build_querystring, resolve_listing_state
from financeiro.forms import (
    CancelBillingForm,
    FinancialPlanForm,
    GenerateBillingsByClassForm,
    PaymentForm,
    RenegotiationForm,
    ReportFilterForm,
)
from financeiro.models import BillingEntry, FinancialPlan
from financeiro.selectors import BillingSelector, FinancialPlanSelector
from financeiro.services import FinanceService, PaymentService

logger = logging.getLogger(__name__)

BILLING_TABS = [
    {"id": "aberto", "label": "Aberto", "status": BillingEntry.Status.OPEN},
    {"id": "vencido", "label": "Vencido", "status": BillingEntry.Status.OVERDUE},
    {"id": "pago", "label": "Pago", "status": BillingEntry.Status.PAID},
    {"id": "cancelado", "label": "Cancelado", "status": BillingEntry.Status.CANCELLED},
]


@login_required
def finance_dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard financeiro com KPIs e atalhos."""
    kpis = BillingSelector().finance_kpis()
    return render(
        request,
        "financeiro/dashboard.html",
        {
            "kpis": kpis,
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": None},
            ],
        },
    )


@login_required
def plan_list(request: HttpRequest) -> HttpResponse:
    """Lista planos financeiros com busca."""
    state = resolve_listing_state(
        request,
        scope="finance_plans",
        allowed_sorts={"name", "-name"},
        default_sort="name",
    )
    search = state["q"]
    page = int(request.GET.get("page", 1))
    status = request.GET.get("status", "")

    result = FinancialPlanSelector().list_plans(search=search, status=status, page=page)
    ctx = {
        "result": result,
        "q": search,
        "status": status,
        "status_choices": FinancialPlan.Status.choices,
        "list_query": build_querystring({"q": search, "status": status}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Financeiro", "url": "finance_dashboard"},
            {"label": "Planos", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "financeiro/partials/plans_table.html", ctx)
    return render(request, "financeiro/plan_list.html", ctx)


@login_required
def plan_create(request: HttpRequest) -> HttpResponse:
    """Cria um plano financeiro."""
    form = FinancialPlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            student = data.pop("student", None)
            class_obj = data.pop("class_obj", None)
            data["student_id"] = student.pk if student else None
            data["class_obj_id"] = class_obj.pk if class_obj else None
            plan = FinanceService(user=request.user).create_plan(data)
            messages.success(request, "Plano financeiro criado.")
            return redirect("plan_detail", pk=plan.pk)
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "financeiro/plan_form.html",
        {"form": form, "title": "Novo Plano Financeiro"},
    )


@login_required
def plan_detail(request: HttpRequest, pk) -> HttpResponse:
    """Detalhe do plano com suas cobrancas."""
    plan = FinancialPlanSelector().get_plan_by_id(pk)
    billings = BillingSelector().get_billings_for_plan(pk)
    return render(
        request,
        "financeiro/plan_detail.html",
        {
            "plan": plan,
            "billings": billings,
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": "finance_dashboard"},
                {"label": "Planos", "url": "plan_list"},
                {"label": plan.name, "url": None},
            ],
        },
    )


@login_required
def plan_activate(request: HttpRequest, pk) -> HttpResponse:
    """Ativa um plano em rascunho."""
    if request.method != "POST":
        return redirect("plan_detail", pk=pk)
    try:
        FinanceService(user=request.user).activate_plan(pk)
        messages.success(request, "Plano ativado.")
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    return redirect("plan_detail", pk=pk)


@login_required
def plan_suspend(request: HttpRequest, pk) -> HttpResponse:
    """Suspende um plano ativo."""
    if request.method != "POST":
        return redirect("plan_detail", pk=pk)
    reason = request.POST.get("reason", "")
    try:
        FinanceService(user=request.user).cancel_plan(pk, reason)
        messages.success(request, "Plano suspenso.")
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    return redirect("plan_detail", pk=pk)


@login_required
def plan_generate_billings(request: HttpRequest, pk) -> HttpResponse:
    """Gerar todas as cobrancas de um plano ativo."""
    if request.method != "POST":
        return redirect("plan_detail", pk=pk)
    try:
        count = FinanceService(user=request.user).generate_billings(pk)
        messages.success(request, f"{count} cobranca(s) gerada(s).")
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    return redirect("plan_detail", pk=pk)


@login_required
def billing_list(request: HttpRequest) -> HttpResponse:
    """Lista cobrancas com tabs por status e busca."""
    tab = request.GET.get("tab", "aberto")
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="finance_billings",
        allowed_sorts={"due_date", "-due_date"},
        default_sort="-due_date",
    )
    search = state["q"]

    tab_map = {t["id"]: t["status"] for t in BILLING_TABS}
    status = tab_map.get(tab, BillingEntry.Status.OPEN)

    result = BillingSelector().list_billings(search=search, status=status, page=page)
    ctx = {
        "result": result,
        "q": search,
        "tab": tab,
        "tabs": BILLING_TABS,
        "list_query": build_querystring({"q": search, "tab": tab}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Financeiro", "url": "finance_dashboard"},
            {"label": "Cobrancas", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "financeiro/partials/billings_table.html", ctx)
    return render(request, "financeiro/billing_list.html", ctx)


@login_required
def billing_detail(request: HttpRequest, pk) -> HttpResponse:
    """Detalhe da cobranca e historico de pagamentos."""
    billing = BillingSelector().get_billing_by_id(pk)
    payments = BillingSelector().get_payments(pk)
    return render(
        request,
        "financeiro/billing_detail.html",
        {
            "billing": billing,
            "payments": payments,
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": "finance_dashboard"},
                {"label": "Cobrancas", "url": "billing_list"},
                {"label": billing.description, "url": None},
            ],
        },
    )


@login_required
def billing_register_payment(request: HttpRequest, pk) -> HttpResponse:
    """Baixa manual de pagamento (parcial ou total)."""
    billing = BillingSelector().get_billing_by_id(pk)
    form = PaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            PaymentService(user=request.user).register_payment(
                pk,
                amount=form.cleaned_data["amount"],
                paid_date=form.cleaned_data["paid_date"],
                payment_method=form.cleaned_data["payment_method"],
                notes=form.cleaned_data.get("notes", ""),
            )
            messages.success(request, "Pagamento registrado.")
            return redirect("billing_detail", pk=pk)
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "financeiro/payment_form.html",
        {"form": form, "billing": billing, "title": "Baixa de Pagamento"},
    )


@login_required
def billing_cancel(request: HttpRequest, pk) -> HttpResponse:
    """Cancela uma cobranca em aberto."""
    billing = BillingSelector().get_billing_by_id(pk)
    form = CancelBillingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            FinanceService(user=request.user).cancel_billing(
                pk, form.cleaned_data.get("reason", "")
            )
            messages.success(request, "Cobranca cancelada.")
            return redirect("billing_detail", pk=pk)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "financeiro/billing_cancel.html",
        {"form": form, "billing": billing},
    )


@login_required
def billing_renegotiate(request: HttpRequest, pk) -> HttpResponse:
    """Renegociacao simples de cobranca em aberto/vencido."""
    billing = BillingSelector().get_billing_by_id(pk)
    form = RenegotiationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            FinanceService(user=request.user).renegotiate_billing(
                pk,
                new_due_date=form.cleaned_data["new_due_date"],
                new_value=form.cleaned_data.get("new_value"),
                installment_count=form.cleaned_data["installment_count"],
            )
            messages.success(request, "Cobranca renegociada com sucesso.")
            return redirect("billing_list")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "financeiro/billing_renegotiate.html",
        {"form": form, "billing": billing, "title": "Renegociar Cobranca"},
    )


@login_required
def billing_apply_late_fees(request: HttpRequest, pk) -> HttpResponse:
    """Aplica multa e juros a uma cobranca vencida."""
    if request.method != "POST":
        return redirect("billing_detail", pk=pk)
    try:
        FinanceService(user=request.user).apply_late_fees(pk)
        messages.success(request, "Multa e juros aplicados.")
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    return redirect("billing_detail", pk=pk)


@login_required
def billing_reconcile_payment(request: HttpRequest, pk, payment_id, action: str) -> HttpResponse:
    """Confirma ou estorna um pagamento registrado."""
    if request.method != "POST":
        return redirect("billing_detail", pk=pk)
    confirmed = action == "confirmar"
    if action not in {"confirmar", "estornar"}:
        messages.error(request, "Acao de conciliacao invalida.")
        return redirect("billing_detail", pk=pk)
    try:
        PaymentService(user=request.user).reconcile(payment_id, confirmed=confirmed)
        if confirmed:
            messages.success(request, "Pagamento conciliado.")
        else:
            messages.success(request, "Pagamento estornado.")
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    return redirect("billing_detail", pk=pk)


@login_required
def bulk_generate_billings(request: HttpRequest) -> HttpResponse:
    """Gera cobrancas em lote por turma e competencia."""
    if request.method == "POST":
        form = GenerateBillingsByClassForm(request.POST)
        if form.is_valid():
            class_obj = form.cleaned_data["class_obj"]
            academic_year = form.cleaned_data["academic_year"]
            month_str = form.cleaned_data.get("month")
            month = int(month_str) if month_str else None
            try:
                count = FinanceService(user=request.user).generate_billings_by_class(
                    class_id=class_obj, academic_year=academic_year, month=month
                )
                messages.success(request, f"{count} cobranca(s) gerada(s) para a turma.")
                return redirect("billing_list")
            except (ObjectNotFoundError, BusinessRuleViolationError, ValidationError) as exc:
                if isinstance(exc, ValidationError):
                    for field, errors in exc.errors.items():
                        for error in errors:
                            form.add_error(field if field != "__all__" else None, error)
                else:
                    messages.error(request, exc.message)
    else:
        initial = {"academic_year": dt.date.today().year}
        form = GenerateBillingsByClassForm(initial=initial)
    return render(
        request,
        "financeiro/bulk_generate.html",
        {
            "form": form,
            "title": "Gerar Cobrancas em Lote",
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": "finance_dashboard"},
                {"label": "Gerar em Lote", "url": None},
            ],
        },
    )


@login_required
def revenue_report(request: HttpRequest) -> HttpResponse:
    """Relatorio mensal de receita prevista x recebida."""
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
    """Relatorio de inadimplencia por faixa de atraso."""
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
