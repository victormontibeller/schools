"""Orquestração HTTP de cobranças contratuais e avulsas."""

import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_listing_tabs, build_querystring, build_sorting, resolve_listing_state
from core.permissions import CREATE, EDIT, VIEW, access_policy, can_access, role_name
from financeiro.constants import BILLING_TABS
from financeiro.forms import (
    AdHocBillingForm,
    CancelBillingForm,
    MaterializeBillingsByClassForm,
    PaymentForm,
    RenegotiationForm,
)
from financeiro.selectors import BillingSelector
from financeiro.services import FinanceService, PaymentService
from financeiro.view_helpers import finance_breadcrumbs


def _service_error(request, form, exc) -> None:
    if isinstance(exc, ValidationError):
        apply_validation_errors(form, exc)
    else:
        messages.error(request, exc.message)


@login_required
@access_policy("finance_billings", VIEW)
def billing_list(request: HttpRequest) -> HttpResponse:
    """Lista cobranças com abas por situação e busca."""
    requested_tab = request.GET.get("tab", BILLING_TABS[0]["id"])
    state = resolve_listing_state(
        request,
        scope="finance_billings",
        allowed_sorts={"due_date", "-due_date", "competency", "-competency"},
        default_sort="-due_date",
    )
    tab_map = {item["id"]: item["status"] for item in BILLING_TABS}
    tab = requested_tab if requested_tab in tab_map else BILLING_TABS[0]["id"]
    result = BillingSelector(user=request.user).list_billings(
        search=state["q"], status=tab_map[tab], order_by=state["sort"], page=state["page"]
    )
    sorting = build_sorting(
        current_sort=state["sort"],
        search=state["q"],
        sortable_fields=["due_date", "competency"],
        preserved_params={"tab": tab},
    )
    values = {"q": state["q"], "tab": tab, "sort": state["sort"]}
    is_htmx = bool(request.headers.get("HX-Request"))
    context = {
        "result": result,
        "q": state["q"],
        "tab": tab,
        "list_tabs": build_listing_tabs(
            choices=((item["id"], item["label"]) for item in BILLING_TABS),
            active=tab,
            parameter="tab",
            preserved_params={"q": state["q"], "sort": state["sort"]},
        ),
        "list_tabs_label": "Situações das cobranças",
        "sort": state["sort"],
        "sorting": sorting,
        "clear_query": build_querystring({"tab": tab, "sort": state["sort"]}),
        "list_query": build_querystring(values),
        "list_hidden_fields": [
            {"name": key, "value": value} for key, value in values.items() if key != "q"
        ],
        "list_table_template": "financeiro/partials/billings_table.html",
        "pagination_target": "#billings-table",
        "pagination_swap": "outerHTML",
        "pagination_push_url": True,
        "is_htmx": is_htmx,
        "breadcrumb_items": finance_breadcrumbs(request.user, ("Cobranças", None)),
    }
    if is_htmx:
        return render(request, "partials/tabbed_list_card.html", context)
    return render(request, "financeiro/billing_list.html", context)


@login_required
@access_policy("finance_billings", CREATE)
def billing_create(request: HttpRequest) -> HttpResponse:
    """Cria cobrança avulsa para um aluno."""
    form = AdHocBillingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        student = data.pop("student")
        data["student_id"] = student.pk
        data["amount"] = data.pop("principal_value")
        try:
            billing = FinanceService(user=request.user).create_ad_hoc_billing(data)
            messages.success(request, "Cobrança avulsa cadastrada.")
            return redirect("billing_detail", pk=billing.pk)
        except (ValidationError, BusinessRuleViolationError) as exc:
            _service_error(request, form, exc)
    return render(
        request,
        "financeiro/generic_form.html",
        {"form": form, "title": "Nova cobrança avulsa", "cancel_url": "billing_list"},
    )


@login_required
@access_policy("finance_billings", VIEW)
def billing_detail(request: HttpRequest, pk) -> HttpResponse:
    """Exibe a cobrança e seu histórico de pagamentos autorizado."""
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
                {"label": "Cobranças", "url": "billing_list"},
                {"label": billing.description, "url": None},
            ],
        },
    )


@login_required
@access_policy("finance_payments", CREATE)
def billing_register_payment(request: HttpRequest, pk) -> HttpResponse:
    """Registra uma baixa manual parcial ou total."""
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
    """Cancela uma cobrança em aberto."""
    billing = BillingSelector(user=request.user).get_billing_by_id(pk)
    form = CancelBillingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            FinanceService(user=request.user).cancel_billing(
                pk, form.cleaned_data.get("reason", "")
            )
            messages.success(request, "Cobrança cancelada.")
            return redirect("billing_detail", pk=pk)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(request, "financeiro/billing_cancel.html", {"form": form, "billing": billing})


@login_required
@access_policy("finance_billings", EDIT)
def billing_renegotiate(request: HttpRequest, pk) -> HttpResponse:
    """Renegocia vencimento e valor de uma cobrança aberta."""
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
            messages.success(request, "Cobrança renegociada com sucesso.")
            return redirect("billing_list")
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "financeiro/billing_renegotiate.html",
        {"form": form, "billing": billing, "title": "Renegociar Cobrança"},
    )


@login_required
@access_policy("finance_billings", EDIT)
def billing_assess_late_charges(request: HttpRequest, pk) -> HttpResponse:
    """Aplica multa e juros a uma cobrança vencida."""
    if request.method == "POST":
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
            month_value = form.cleaned_data.get("month")
            try:
                count = FinanceService(user=request.user).materialize_billings_by_class(
                    class_id=form.cleaned_data["class_obj"],
                    academic_year=form.cleaned_data["academic_year"],
                    month=int(month_value) if month_value else None,
                )
                messages.success(request, f"{count} cobrança(s) gerada(s) para a turma.")
                return redirect("billing_list")
            except (ObjectNotFoundError, BusinessRuleViolationError, ValidationError) as exc:
                _service_error(request, form, exc)
    else:
        form = MaterializeBillingsByClassForm(initial={"academic_year": dt.date.today().year})
    return render(
        request,
        "financeiro/bulk_generate.html",
        {
            "form": form,
            "title": "Gerar Cobranças em Lote",
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Financeiro", "url": "finance_dashboard"},
                {"label": "Gerar em Lote", "url": None},
            ],
        },
    )
