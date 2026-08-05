"""Orquestração HTTP de baixas e conciliações financeiras."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_listing_tabs, build_querystring, build_sorting, resolve_listing_state
from core.permissions import CREATE, EDIT, VIEW, access_policy
from financeiro.forms import PaymentBatchForm, PaymentReversalForm
from financeiro.selectors import BillingSelector, PaymentSelector
from financeiro.services import PaymentService
from financeiro.view_helpers import finance_breadcrumbs


def _service_error(request, form, exc) -> None:
    if isinstance(exc, ValidationError):
        apply_validation_errors(form, exc)
    else:
        messages.error(request, exc.message)


@login_required
@access_policy("finance_payments", CREATE)
def payment_create(request: HttpRequest) -> HttpResponse:
    """Registra uma baixa distribuída entre cobranças abertas."""
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
    """Lista baixas por situação de conciliação."""
    from financeiro.contracts import PaymentRecord

    state = resolve_listing_state(
        request,
        scope="financial_payments",
        allowed_sorts={"paid_date", "-paid_date", "amount", "-amount"},
        default_sort="-paid_date",
    )
    status_choices = list(PaymentRecord.Status.choices)
    allowed = {value for value, _label in status_choices}
    requested = request.GET.get("status", PaymentRecord.Status.PENDING)
    status = requested if requested in allowed else PaymentRecord.Status.PENDING
    result = PaymentSelector(user=request.user).list_payments(
        search=state["q"], status=status, order_by=state["sort"], page=state["page"]
    )
    sorting = build_sorting(
        current_sort=state["sort"],
        search=state["q"],
        sortable_fields=["paid_date", "amount"],
        preserved_params={"status": status},
    )
    values = {"q": state["q"], "status": status, "sort": state["sort"]}
    is_htmx = bool(request.headers.get("HX-Request"))
    context = {
        "result": result,
        "status": status,
        "list_tabs": build_listing_tabs(
            choices=status_choices,
            active=status,
            parameter="status",
            preserved_params={"q": state["q"], "sort": state["sort"]},
        ),
        "list_tabs_label": "Situações das conciliações",
        "q": state["q"],
        "sort": state["sort"],
        "sorting": sorting,
        "clear_query": build_querystring({"status": status, "sort": state["sort"]}),
        "list_query": build_querystring(values),
        "list_hidden_fields": [
            {"name": key, "value": value} for key, value in values.items() if key != "q"
        ],
        "list_table_template": "financeiro/partials/payments_table.html",
        "pagination_target": "#payments-table",
        "pagination_swap": "outerHTML",
        "pagination_push_url": True,
        "is_htmx": is_htmx,
        "breadcrumb_items": finance_breadcrumbs(request.user, ("Baixas e Conciliações", None)),
    }
    if is_htmx:
        return render(request, "partials/tabbed_list_card.html", context)
    return render(request, "financeiro/payment_list.html", context)


@login_required
@access_policy("finance_payments", VIEW)
def payment_detail(request: HttpRequest, pk) -> HttpResponse:
    """Exibe a baixa e suas alocações."""
    return render(
        request,
        "financeiro/payment_detail.html",
        {"payment": PaymentSelector(user=request.user).get_payment(pk)},
    )


@login_required
@access_policy("finance_payments", EDIT)
def payment_confirm(request: HttpRequest, pk) -> HttpResponse:
    """Confirma a baixa e emite recibo interno."""
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
    """Estorna uma baixa confirmada preservando seu histórico."""
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
