"""Orquestração HTTP dos modelos financeiros reutilizáveis."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_querystring, build_sorting, resolve_listing_state
from core.permissions import CREATE, EDIT, VIEW, access_policy
from financeiro.forms import FinancialPlanTemplateForm
from financeiro.selectors import FinancialTemplateSelector
from financeiro.services import FinanceService
from financeiro.view_helpers import finance_breadcrumbs


def _service_error(request, form, exc) -> None:
    if isinstance(exc, ValidationError):
        apply_validation_errors(form, exc)
    else:
        messages.error(request, exc.message)


@login_required
@access_policy("finance_templates", VIEW)
def financial_template_list(request: HttpRequest) -> HttpResponse:
    """Lista modelos financeiros com busca e ordenação."""
    state = resolve_listing_state(
        request,
        scope="financial_templates",
        allowed_sorts={"name", "-name", "academic_year", "-academic_year"},
        default_sort="-academic_year",
    )
    result = FinancialTemplateSelector().list_templates(
        search=state["q"],
        year=request.GET.get("year") or None,
        order_by=state["sort"],
        page=state["page"],
    )
    sorting = build_sorting(
        current_sort=state["sort"],
        search=state["q"],
        sortable_fields=["name", "academic_year"],
    )
    if request.GET.get("year"):
        for item in sorting.values():
            item["query"] += f"&year={request.GET['year']}"
    context = {
        "result": result,
        "q": state["q"],
        "sort": state["sort"],
        "sorting": sorting,
        "list_query": build_querystring({"q": state["q"], "sort": state["sort"]}),
        "breadcrumb_items": finance_breadcrumbs(request.user, ("Modelos", None)),
    }
    if request.headers.get("HX-Request"):
        return render(request, "financeiro/partials/templates_table.html", context)
    return render(request, "financeiro/template_list.html", context)


@login_required
@access_policy("finance_templates", CREATE)
def financial_template_create(request: HttpRequest) -> HttpResponse:
    """Cria um modelo financeiro reutilizável."""
    form = FinancialPlanTemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            template = FinanceService(user=request.user).create_financial_template(
                form.cleaned_data
            )
            messages.success(request, "Modelo financeiro cadastrado.")
            return redirect("financial_template_detail", pk=template.pk)
        except (ValidationError, BusinessRuleViolationError) as exc:
            _service_error(request, form, exc)
    return render(
        request,
        "financeiro/generic_form.html",
        {"form": form, "title": "Novo modelo financeiro", "cancel_url": "financial_template_list"},
    )


@login_required
@access_policy("finance_templates", VIEW)
def financial_template_detail(request: HttpRequest, pk) -> HttpResponse:
    """Exibe os termos do modelo financeiro."""
    item = FinancialTemplateSelector().get_template(pk)
    return render(request, "financeiro/template_detail.html", {"item": item})


@login_required
@access_policy("finance_templates", EDIT)
def financial_template_edit(request: HttpRequest, pk) -> HttpResponse:
    """Atualiza um modelo sem reescrever contratos existentes."""
    item = FinancialTemplateSelector().get_template(pk)
    form = FinancialPlanTemplateForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        try:
            FinanceService(user=request.user).update_financial_template(
                pk, {**form.cleaned_data, "version": item.version}
            )
            messages.success(
                request, "Modelo atualizado; contratos existentes não foram alterados."
            )
            return redirect("financial_template_detail", pk=pk)
        except (ValidationError, BusinessRuleViolationError) as exc:
            _service_error(request, form, exc)
    return render(
        request,
        "financeiro/generic_form.html",
        {"form": form, "title": "Editar modelo financeiro", "cancel_pk": pk},
    )
