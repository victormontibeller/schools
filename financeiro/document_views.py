"""Extratos, recibos e disparo manual vinculados às fichas financeiras."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from core.permissions import EDIT, VIEW, access_policy, role_name
from financeiro.selectors import BillingSelector, PaymentSelector
from financeiro.services import FinanceService


@login_required
@access_policy("finance_reminders", EDIT)
def billing_send_reminder(request: HttpRequest, pk) -> HttpResponse:
    if request.method == "POST":
        try:
            count = FinanceService(user=request.user).send_manual_reminder(pk)
            messages.success(request, f"{count} lembrete(s) enfileirado(s).")
        except (ValidationError, BusinessRuleViolationError, ObjectNotFoundError) as exc:
            messages.error(request, exc.message)
    return redirect("billing_detail", pk=pk)


def _scoped_student(request, student_id):
    from core.access_selectors import ObjectAccessSelector
    from students.selectors import StudentSelector

    if role_name(
        request.user
    ) == "GUARDIAN" and not ObjectAccessSelector.guardian_can_access_student(
        request.user.pk, student_id
    ):
        raise PermissionDenied("Aluno não vinculado a este responsável.")
    return StudentSelector().get_student_by_id(student_id)


@login_required
@access_policy("finance_billings", VIEW)
def student_statement(request: HttpRequest, student_id) -> HttpResponse:
    student = _scoped_student(request, student_id)
    billings = BillingSelector(user=request.user).student_statement(student_id)
    guardian_view = role_name(request.user) == "GUARDIAN"
    return render(
        request,
        "financeiro/student_statement.html",
        {"student": student, "billings": billings, "guardian_view": guardian_view},
    )


@login_required
@access_policy("finance_billings", VIEW)
def student_statement_pdf(request: HttpRequest, student_id) -> HttpResponse:
    from financeiro.pdf_documents import render_student_statement

    student = _scoped_student(request, student_id)
    billings = BillingSelector(user=request.user).student_statement(student_id)
    school_name = getattr(getattr(request, "tenant", None), "name", "Escola")
    response = HttpResponse(
        render_student_statement(student, billings, school_name=school_name),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'inline; filename="extrato-{student.pk}.pdf"'
    return response


@login_required
@access_policy("finance_billings", VIEW)
def payment_receipt_pdf(request: HttpRequest, pk) -> HttpResponse:
    from financeiro.contracts import PaymentRecord
    from financeiro.pdf_documents import render_payment_receipt

    payment = PaymentSelector(user=request.user).get_payment(pk)
    if payment.status == PaymentRecord.Status.PENDING:
        raise ObjectNotFoundError("PaymentRecord", str(pk))
    school_name = getattr(getattr(request, "tenant", None), "name", "Escola")
    response = HttpResponse(
        render_payment_receipt(payment, school_name=school_name), content_type="application/pdf"
    )
    response["Content-Disposition"] = (
        f'inline; filename="{payment.receipt_number or payment.pk}.pdf"'
    )
    return response
