"""Views operacionais do contas a receber e documentos autenticados."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_querystring, build_sorting, resolve_listing_state
from core.permissions import CREATE, EDIT, VIEW, access_policy
from financeiro.forms import (
    AdHocBillingForm,
    CollectionReminderPolicyForm,
    FinancialContractAmendmentForm,
    FinancialPlanTemplateForm,
    PaymentBatchForm,
    PaymentReversalForm,
    StudentFinancialContractForm,
)
from financeiro.selectors import (
    BillingSelector,
    FinancialContractSelector,
    FinancialTemplateSelector,
    PaymentSelector,
    ReminderSelector,
)
from financeiro.services import FinanceService, PaymentService
from financeiro.view_helpers import finance_breadcrumbs


def _service_error(request, form, exc):
    if isinstance(exc, ValidationError):
        apply_validation_errors(form, exc)
    else:
        messages.error(request, exc.message)


@login_required
@access_policy("finance_templates", VIEW)
def financial_template_list(request: HttpRequest) -> HttpResponse:
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
        page=int(request.GET.get("page", 1)),
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
    item = FinancialTemplateSelector().get_template(pk)
    return render(request, "financeiro/template_detail.html", {"item": item})


@login_required
@access_policy("finance_templates", EDIT)
def financial_template_edit(request: HttpRequest, pk) -> HttpResponse:
    item = FinancialTemplateSelector().get_template(pk)
    form = FinancialPlanTemplateForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        try:
            data = {**form.cleaned_data, "version": item.version}
            FinanceService(user=request.user).update_financial_template(pk, data)
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


@login_required
@access_policy("finance_contracts", EDIT)
def contract_edit(request: HttpRequest, pk) -> HttpResponse:
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
def contract_amendment_create(request: HttpRequest, pk) -> HttpResponse:
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


@login_required
@access_policy("finance_billings", CREATE)
def ad_hoc_billing_create(request: HttpRequest) -> HttpResponse:
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
@access_policy("finance_payments", CREATE)
def payment_create(request: HttpRequest) -> HttpResponse:
    from students.selectors import StudentSelector

    student_id = request.POST.get("student_id") or request.GET.get("student_id")
    students = StudentSelector().list_students(page_size=100).items
    billings = BillingSelector(user=request.user).open_for_student(student_id) if student_id else []
    form = PaymentBatchForm(request.POST or None, billings=billings)
    if request.method == "POST" and form.is_valid():
        try:
            PaymentService(user=request.user).create_payment(
                allocations=form.allocations,
                paid_date=form.cleaned_data["paid_date"],
                payment_method=form.cleaned_data["payment_method"],
                reference=form.cleaned_data["reference"],
                idempotency_key=form.cleaned_data["idempotency_key"],
            )
            messages.success(request, "Baixa registrada e aguardando conciliação.")
            return redirect("payment_queue")
        except (ValidationError, BusinessRuleViolationError, ObjectNotFoundError) as exc:
            _service_error(request, form, exc)
    return render(
        request,
        "financeiro/payment_batch_form.html",
        {
            "form": form,
            "students": students,
            "student_id": str(student_id or ""),
            "allocation_rows": [
                {"billing": billing, "field": form[f"allocation_{billing.pk}"]}
                for billing in billings
            ],
        },
    )


@login_required
@access_policy("finance_payments", VIEW)
def payment_queue(request: HttpRequest) -> HttpResponse:
    from financeiro.contracts import PaymentRecord

    state = resolve_listing_state(
        request,
        scope="financial_payments",
        allowed_sorts={"paid_date", "-paid_date", "amount", "-amount"},
        default_sort="-paid_date",
    )
    status = request.GET.get("status", "PENDING")
    result = PaymentSelector(user=request.user).list_payments(
        search=state["q"],
        status=status,
        order_by=state["sort"],
        page=int(request.GET.get("page", 1)),
    )
    sorting = build_sorting(
        current_sort=state["sort"],
        search=state["q"],
        sortable_fields=["paid_date", "amount"],
    )
    if status:
        for item in sorting.values():
            item["query"] += f"&status={status}"
    context = {
        "result": result,
        "status": status,
        "status_choices": PaymentRecord.Status.choices,
        "q": state["q"],
        "sort": state["sort"],
        "sorting": sorting,
        "breadcrumb_items": finance_breadcrumbs(request.user, ("Baixas e Conciliações", None)),
    }
    if request.headers.get("HX-Request"):
        return render(request, "financeiro/partials/payments_table.html", context)
    return render(request, "financeiro/payment_list.html", context)


@login_required
@access_policy("finance_payments", VIEW)
def payment_detail(request: HttpRequest, pk) -> HttpResponse:
    payment = PaymentSelector(user=request.user).get_payment(pk)
    return render(request, "financeiro/payment_detail.html", {"payment": payment})


@login_required
@access_policy("finance_payments", EDIT)
def payment_confirm(request: HttpRequest, pk) -> HttpResponse:
    if request.method == "POST":
        try:
            PaymentService(user=request.user).confirm_payment(pk)
            messages.success(request, "Pagamento conciliado e recibo emitido.")
        except (ValidationError, BusinessRuleViolationError, ObjectNotFoundError) as exc:
            messages.error(request, exc.message)
    return redirect("payment_queue")


@login_required
@access_policy("finance_payments", EDIT)
def payment_reverse(request: HttpRequest, pk) -> HttpResponse:
    payment = PaymentSelector(user=request.user).get_payment(pk)
    form = PaymentReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            PaymentService(user=request.user).reverse_payment(
                pk, reason=form.cleaned_data["reason"]
            )
            messages.success(request, "Pagamento estornado; o movimento negativo foi registrado.")
            return redirect("payment_queue")
        except (BusinessRuleViolationError, ObjectNotFoundError, ValidationError) as exc:
            _service_error(request, form, exc)
    return render(
        request,
        "financeiro/generic_form.html",
        {
            "form": form,
            "title": "Estornar pagamento",
            "payment": payment,
            "cancel_url": "payment_queue",
        },
    )


@login_required
@access_policy("finance_reminders", EDIT)
def reminder_settings(request: HttpRequest) -> HttpResponse:
    policy = ReminderSelector().get_policy()
    form = CollectionReminderPolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        try:
            FinanceService(user=request.user).configure_reminder_policy(
                {
                    "name": form.cleaned_data["name"],
                    "enabled": form.cleaned_data["enabled"],
                    "channels": form.cleaned_data["channels"],
                    "offset_days": form.cleaned_data["offset_days_text"],
                }
            )
            messages.success(request, "Régua de cobrança atualizada.")
            return redirect("reminder_settings")
        except (ValidationError, BusinessRuleViolationError) as exc:
            _service_error(request, form, exc)
    return render(request, "financeiro/reminder_settings.html", {"form": form, "policy": policy})


@login_required
@access_policy("finance_reminders", VIEW)
def reminder_history(request: HttpRequest) -> HttpResponse:
    from financeiro.contracts import CollectionReminder

    state = resolve_listing_state(
        request,
        scope="financial_reminders",
        allowed_sorts={"scheduled_for", "-scheduled_for", "status", "-status"},
        default_sort="-scheduled_for",
    )
    result = ReminderSelector().list_reminders(
        search=state["q"],
        status=request.GET.get("status", ""),
        order_by=state["sort"],
        page=int(request.GET.get("page", 1)),
    )
    sorting = build_sorting(
        current_sort=state["sort"],
        search=state["q"],
        sortable_fields=["scheduled_for", "status"],
    )
    status = request.GET.get("status", "")
    if status:
        for item in sorting.values():
            item["query"] += f"&status={status}"
    context = {
        "result": result,
        "status": status,
        "q": state["q"],
        "sort": state["sort"],
        "sorting": sorting,
        "status_choices": CollectionReminder.Status.choices,
        "breadcrumb_items": finance_breadcrumbs(request.user, ("Lembretes", None)),
    }
    if request.headers.get("HX-Request"):
        return render(request, "financeiro/partials/reminders_table.html", context)
    return render(request, "financeiro/reminder_list.html", context)
