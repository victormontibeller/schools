"""Orquestração HTTP do ciclo de contratos financeiros."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_querystring, build_sorting, resolve_listing_state
from core.permissions import CREATE, EDIT, VIEW, access_policy, can_access
from financeiro.contracts import StudentFinancialContract
from financeiro.forms import FinancialContractAmendmentForm, StudentFinancialContractForm
from financeiro.selectors import BillingSelector, FinancialContractSelector
from financeiro.services import FinanceService
from financeiro.view_helpers import finance_breadcrumbs


def _service_error(request, form, exc) -> None:
    if isinstance(exc, ValidationError):
        apply_validation_errors(form, exc)
    else:
        messages.error(request, exc.message)


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
    status = request.GET.get("status", "")
    result = FinancialContractSelector(user=request.user).list_contracts(
        search=search, status=status, order_by=state["sort"], page=state["page"]
    )
    sorting = build_sorting(
        current_sort=state["sort"], search=search, sortable_fields=["name", "academic_year"]
    )
    if status:
        for item in sorting.values():
            item["query"] += f"&status={status}"
    context = {
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
        return render(request, "financeiro/partials/contracts_table.html", context)
    return render(request, "financeiro/contract_list.html", context)


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
            data.update(
                student_id=student.pk if student else None,
                template_id=template.pk if template else None,
                class_obj_id=class_obj.pk if class_obj else None,
            )
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
    """Detalha o contrato e suas cobranças quando autorizadas."""
    contract = FinancialContractSelector(user=request.user).get_contract(pk)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request, "financeiro/partials/contract_information_card.html", {"contract": contract}
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
def contract_edit(request: HttpRequest, pk) -> HttpResponse:
    """Edita somente o card de informações de um contrato em rascunho."""
    contract = FinancialContractSelector(user=request.user).get_contract(pk)
    form = StudentFinancialContractForm(request.POST or None, instance=contract)
    form.fields["student"].disabled = True
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        class_obj = data.pop("class_obj", None)
        data.pop("student", None)
        data.pop("template", None)
        data["class_obj_id"] = class_obj.pk if class_obj else None
        try:
            contract = FinanceService(user=request.user).update_contract_draft(pk, data)
            if request.headers.get("HX-Request"):
                return render(
                    request,
                    "financeiro/partials/contract_information_card.html",
                    {"contract": contract, "saved": True},
                )
            messages.success(request, "Rascunho atualizado.")
            return redirect("contract_detail", pk=pk)
        except (ValidationError, BusinessRuleViolationError) as exc:
            _service_error(request, form, exc)
    context = {
        "contract": contract,
        "form": form,
        "cancel_url": f"{reverse('contract_detail', args=[pk])}?component=information",
    }
    if request.headers.get("HX-Request"):
        return render(
            request,
            "partials/information_form_card.html",
            {
                **context,
                "component_id": "contract-information-card",
                "component_title": "Informações do contrato",
                "edit_url": request.path,
            },
        )
    return render(request, "financeiro/contract_edit.html", context)


@login_required
@access_policy("finance_contracts", EDIT)
def contract_activate(request: HttpRequest, pk) -> HttpResponse:
    """Ativa um contrato em rascunho."""
    if request.method == "POST":
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
    if request.method == "POST":
        try:
            FinanceService(user=request.user).suspend_contract(pk, request.POST.get("reason", ""))
            messages.success(request, "Contrato suspenso.")
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return redirect("contract_detail", pk=pk)


@login_required
@access_policy("finance_billings", CREATE)
def contract_materialize_billings(request: HttpRequest, pk) -> HttpResponse:
    """Materializa todas as cobranças de um contrato ativo."""
    if request.method == "POST":
        try:
            count = FinanceService(user=request.user).materialize_contract_billings(pk)
            messages.success(request, f"{count} cobrança(s) gerada(s).")
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return redirect("contract_detail", pk=pk)


@login_required
@access_policy("finance_contracts", EDIT)
def contract_amendment_create(request: HttpRequest, pk) -> HttpResponse:
    """Cria um aditivo e substitui somente cobranças futuras."""
    contract = FinancialContractSelector(user=request.user).get_contract(pk)
    form = FinancialContractAmendmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = {
            "effective_competency": form.cleaned_data["effective_competency"],
            "reason": form.cleaned_data["reason"],
            **form.changed_terms,
        }
        try:
            FinanceService(user=request.user).create_amendment(pk, data)
            messages.success(request, "Aditivo criado e cobranças futuras substituídas.")
            return redirect("contract_detail", pk=pk)
        except (ValidationError, BusinessRuleViolationError) as exc:
            _service_error(request, form, exc)
    return render(
        request,
        "financeiro/contract_amendment_form.html",
        {"contract": contract, "form": form},
    )
