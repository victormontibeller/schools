"""Views HTMX do modulo Financeiro Escolar — secretaria/financeiro."""

import datetime as dt
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_querystring, build_sorting, resolve_listing_state
from core.permissions import CREATE, EDIT, VIEW, access_policy, can_access, role_name
from financeiro.constants import BILLING_TABS
from financeiro.contracts import StudentFinancialContract
from financeiro.forms import (
    CancelBillingForm,
    MaterializeBillingsByClassForm,
    PaymentForm,
    RenegotiationForm,
    StudentFinancialContractForm,
)
from financeiro.selectors import BillingSelector, FinancialContractSelector
from financeiro.services import FinanceService, PaymentService
from financeiro.view_helpers import finance_breadcrumbs

logger = logging.getLogger(__name__)


@login_required
@access_policy("finance_overview", VIEW)
def finance_dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard financeiro com KPIs e atalhos."""
    kpis = BillingSelector(user=request.user).finance_kpis()
    return render(
        request,
        "financeiro/dashboard.html",
        {
            "kpis": kpis,
            "guardian_view": role_name(request.user) == "GUARDIAN",
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": None},
            ],
        },
    )


@login_required
@access_policy("finance_contracts", VIEW)
def contract_list(request: HttpRequest) -> HttpResponse:
    """Lista contratos financeiros com busca."""
    state = resolve_listing_state(
        request,
        scope="finance_contracts",
        allowed_sorts={"name", "-name", "academic_year", "-academic_year"},
        default_sort="name",
    )
    search = state["q"]
    page = int(request.GET.get("page", 1))
    status = request.GET.get("status", "")

    result = FinancialContractSelector(user=request.user).list_contracts(
        search=search, status=status, order_by=state["sort"], page=page
    )
    sorting = build_sorting(
        current_sort=state["sort"], search=search, sortable_fields=["name", "academic_year"]
    )
    if status:
        for item in sorting.values():
            item["query"] += f"&status={status}"
    ctx = {
        "result": result,
        "q": search,
        "status": status,
        "status_choices": StudentFinancialContract.Status.choices,
        "sort": state["sort"],
        "sorting": sorting,
        "list_query": build_querystring({"q": search, "status": status, "sort": state["sort"]}),
        "breadcrumb_items": finance_breadcrumbs(request.user, ("Contratos", None)),
    }
    if request.headers.get("HX-Request"):
        return render(request, "financeiro/partials/contracts_table.html", ctx)
    return render(request, "financeiro/contract_list.html", ctx)


@login_required
@access_policy("finance_contracts", CREATE)
def contract_create(request: HttpRequest) -> HttpResponse:
    """Cria um contrato financeiro."""
    form = StudentFinancialContractForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            template = data.pop("template", None)
            student = data.pop("student", None)
            class_obj = data.pop("class_obj", None)
            data["student_id"] = student.pk if student else None
            data["template_id"] = template.pk if template else None
            data["class_obj_id"] = class_obj.pk if class_obj else None
            contract = FinanceService(user=request.user).create_contract(data)
            messages.success(request, "Contrato financeiro criado em rascunho.")
            return redirect("contract_detail", pk=contract.pk)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "financeiro/contract_form.html",
        {"form": form, "title": "Novo contrato financeiro"},
    )


@login_required
@access_policy("finance_contracts", VIEW)
def contract_detail(request: HttpRequest, pk) -> HttpResponse:
    """Detalha o contrato com suas cobranças."""
    contract = FinancialContractSelector(user=request.user).get_contract(pk)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "financeiro/partials/contract_information_card.html",
            {"contract": contract},
        )
    can_view_billings = can_access(request.user, "finance_billings", VIEW)
    billings = (
        BillingSelector(user=request.user).get_billings_for_contract(pk)
        if can_view_billings
        else None
    )
    return render(
        request,
        "financeiro/contract_detail.html",
        {
            "contract": contract,
            "billings": billings,
            "can_view_billings": can_view_billings,
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": "finance_dashboard"},
                {"label": "Contratos", "url": "contract_list"},
                {"label": contract.name, "url": None},
            ],
        },
    )


@login_required
@access_policy("finance_contracts", EDIT)
def contract_activate(request: HttpRequest, pk) -> HttpResponse:
    """Ativa um contrato em rascunho."""
    if request.method != "POST":
        return redirect("contract_detail", pk=pk)
    try:
        FinanceService(user=request.user).activate_contract(pk)
        messages.success(request, "Contrato ativado.")
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    return redirect("contract_detail", pk=pk)


@login_required
@access_policy("finance_contracts", EDIT)
def contract_suspend(request: HttpRequest, pk) -> HttpResponse:
    """Suspende um contrato ativo."""
    if request.method != "POST":
        return redirect("contract_detail", pk=pk)
    reason = request.POST.get("reason", "")
    try:
        FinanceService(user=request.user).suspend_contract(pk, reason)
        messages.success(request, "Contrato suspenso.")
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    return redirect("contract_detail", pk=pk)


@login_required
@access_policy("finance_billings", CREATE)
def contract_materialize_billings(request: HttpRequest, pk) -> HttpResponse:
    """Materializa todas as cobranças de um contrato ativo."""
    if request.method != "POST":
        return redirect("contract_detail", pk=pk)
    try:
        count = FinanceService(user=request.user).materialize_contract_billings(pk)
        messages.success(request, f"{count} cobranca(s) gerada(s).")
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    return redirect("contract_detail", pk=pk)


@login_required
@access_policy("finance_billings", VIEW)
def billing_list(request: HttpRequest) -> HttpResponse:
    """Lista cobrancas com tabs por status e busca."""
    tab = request.GET.get("tab", "aberto")
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="finance_billings",
        allowed_sorts={"due_date", "-due_date", "competency", "-competency"},
        default_sort="-due_date",
    )
    search = state["q"]

    tab_map = {t["id"]: t["status"] for t in BILLING_TABS}
    status = tab_map.get(tab, "OPEN")

    result = BillingSelector(user=request.user).list_billings(
        search=search, status=status, order_by=state["sort"], page=page
    )
    sorting = build_sorting(
        current_sort=state["sort"],
        search=search,
        sortable_fields=["due_date", "competency"],
    )
    for item in sorting.values():
        item["query"] += f"&tab={tab}"
    ctx = {
        "result": result,
        "q": search,
        "tab": tab,
        "tabs": BILLING_TABS,
        "sort": state["sort"],
        "sorting": sorting,
        "list_query": build_querystring({"q": search, "tab": tab, "sort": state["sort"]}),
        "breadcrumb_items": finance_breadcrumbs(request.user, ("Cobranças", None)),
    }
    if request.headers.get("HX-Request"):
        return render(request, "financeiro/partials/billings_table.html", ctx)
    return render(request, "financeiro/billing_list.html", ctx)


@login_required
@access_policy("finance_billings", VIEW)
def billing_detail(request: HttpRequest, pk) -> HttpResponse:
    """Detalhe da cobranca e historico de pagamentos."""
    billing = BillingSelector(user=request.user).get_billing_by_id(pk)
    can_view_payments = can_access(request.user, "finance_payments", VIEW)
    payments = BillingSelector(user=request.user).get_payments(pk) if can_view_payments else None
    return render(
        request,
        "financeiro/billing_detail.html",
        {
            "billing": billing,
            "payments": payments,
            "can_view_payments": can_view_payments,
            "guardian_view": role_name(request.user) == "GUARDIAN",
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": "finance_dashboard"},
                {"label": "Cobrancas", "url": "billing_list"},
                {"label": billing.description, "url": None},
            ],
        },
    )


@login_required
@access_policy("finance_payments", CREATE)
def billing_register_payment(request: HttpRequest, pk) -> HttpResponse:
    """Baixa manual de pagamento (parcial ou total)."""
    billing = BillingSelector(user=request.user).get_billing_by_id(pk)
    form = PaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            PaymentService(user=request.user).create_payment(
                allocations=[{"billing_id": pk, "amount": form.cleaned_data["amount"]}],
                paid_date=form.cleaned_data["paid_date"],
                payment_method=form.cleaned_data["payment_method"],
                reference=form.cleaned_data.get("reference", ""),
                notes=form.cleaned_data.get("notes", ""),
                idempotency_key=form.cleaned_data["idempotency_key"],
            )
            messages.success(request, "Baixa registrada e aguardando conciliação.")
            return redirect("payment_queue")
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "financeiro/payment_form.html",
        {"form": form, "billing": billing, "title": "Baixa de Pagamento"},
    )


@login_required
@access_policy("finance_billings", EDIT)
def billing_cancel(request: HttpRequest, pk) -> HttpResponse:
    """Cancela uma cobranca em aberto."""
    billing = BillingSelector(user=request.user).get_billing_by_id(pk)
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
@access_policy("finance_billings", EDIT)
def billing_renegotiate(request: HttpRequest, pk) -> HttpResponse:
    """Renegociacao simples de cobranca em aberto/vencido."""
    billing = BillingSelector(user=request.user).get_billing_by_id(pk)
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
            apply_validation_errors(form, exc)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "financeiro/billing_renegotiate.html",
        {"form": form, "billing": billing, "title": "Renegociar Cobranca"},
    )


@login_required
@access_policy("finance_billings", EDIT)
def billing_assess_late_charges(request: HttpRequest, pk) -> HttpResponse:
    """Aplica multa e juros a uma cobranca vencida."""
    if request.method != "POST":
        return redirect("billing_detail", pk=pk)
    try:
        FinanceService(user=request.user).assess_late_charges(pk)
        messages.success(request, "Multa e juros aplicados.")
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    return redirect("billing_detail", pk=pk)


@login_required
@access_policy("finance_billings", CREATE)
def bulk_materialize_billings(request: HttpRequest) -> HttpResponse:
    """Materializa cobranças em lote por turma e competência."""
    if request.method == "POST":
        form = MaterializeBillingsByClassForm(request.POST)
        if form.is_valid():
            class_obj = form.cleaned_data["class_obj"]
            academic_year = form.cleaned_data["academic_year"]
            month_str = form.cleaned_data.get("month")
            month = int(month_str) if month_str else None
            try:
                count = FinanceService(user=request.user).materialize_billings_by_class(
                    class_id=class_obj, academic_year=academic_year, month=month
                )
                messages.success(request, f"{count} cobranca(s) gerada(s) para a turma.")
                return redirect("billing_list")
            except (ObjectNotFoundError, BusinessRuleViolationError, ValidationError) as exc:
                if isinstance(exc, ValidationError):
                    apply_validation_errors(form, exc)
                else:
                    messages.error(request, exc.message)
    else:
        initial = {"academic_year": dt.date.today().year}
        form = MaterializeBillingsByClassForm(initial=initial)
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
