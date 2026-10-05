"""Regressões de agenda, encargos e recomposição de estorno."""

import datetime as dt
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from freezegun import freeze_time

from base.exceptions import BusinessRuleViolationError, ValidationError
from classes.models import Class
from financeiro.models import BillingEntry, PaymentRecord
from financeiro.services import FinanceService, PaymentService
from financeiro.tests.test_receivables_v2 import _contract, _student

pytestmark = pytest.mark.django_db


@freeze_time("2026-01-01")
@pytest.mark.parametrize("by_class", [False, True])
def test_materialize_preserves_all_revisions_and_cancelled_titles(user, by_class):
    service = FinanceService(user=user)
    cls = Class.objects.create(name="Financial", academic_year=2026)
    contract = _contract(user, _student(user), class_obj_id=cls.pk)
    service.create_amendment(
        contract.pk,
        {
            "effective_competency": dt.date(2026, 7, 1),
            "reason": "Terms",
            "installment_value": "110",
        },
    )
    if by_class:
        assert service.materialize_billings_by_class(cls.pk, 2026, month=1) == 0
    else:
        assert service.materialize_contract_billings(contract.pk) == 0
    assert BillingEntry.objects.filter(contract=contract, status="ACTIVE").count() == 12
    first = BillingEntry.objects.get(contract=contract, installment_number=1)
    service.cancel_billing(first.pk, "Cancel")
    assert service.materialize_contract_billings(contract.pk) == 0


@freeze_time("2026-01-01")
def test_amendment_preserves_historical_rates_and_monotonic_effective_date(user):
    service = FinanceService(user=user)
    contract = _contract(user, _student(user), daily_interest_percent=0)
    old = contract.billings.get(installment_number=1)
    service.create_amendment(
        contract.pk,
        {"effective_competency": dt.date(2026, 7, 1), "reason": "Rates", "late_fee_percent": "10"},
    )
    service.assess_late_charges(old.pk, reference_date=dt.date(2026, 6, 1))
    old.refresh_from_db()
    assert old.late_fee_value == Decimal("2")
    assert old.late_fee_percent == Decimal("2")
    with pytest.raises(ValidationError):
        service.create_amendment(
            contract.pk,
            {
                "effective_competency": dt.date(2026, 6, 1),
                "reason": "Backwards",
                "late_fee_percent": "20",
            },
        )


@freeze_time("2026-01-01")
def test_amendment_never_recreates_renegotiated_schedule(user):
    service = FinanceService(user=user)
    contract = _contract(user, _student(user))
    source = contract.billings.get(installment_number=8)
    replacements = service.renegotiate_billing(source.pk, new_due_date=dt.date(2026, 8, 1))
    before = replacements[0].principal_value
    service.create_amendment(
        contract.pk,
        {
            "effective_competency": dt.date(2026, 7, 1),
            "reason": "Rates",
            "installment_value": "200",
        },
    )
    replacements[0].refresh_from_db()
    assert replacements[0].principal_value == before
    assert replacements[0].status == "ACTIVE"
    assert contract.billings.filter(installment_number=8).count() == 1


def _renegotiated_payment(user, *, principal="100", fee="0", interest="0", amount="40"):
    service = FinanceService(user=user)
    billing = service.create_ad_hoc_billing(
        {
            "student_id": _student(user).pk,
            "description": "Original",
            "amount": principal,
            "due_date": timezone.localdate(),
        }
    )
    billing.late_fee_value = Decimal(fee)
    billing.interest_value = Decimal(interest)
    billing.save()
    payments = PaymentService(user=user)
    payment = payments.create_payment(
        allocations=[{"billing_id": billing.pk, "amount": amount}], paid_date=timezone.localdate()
    )
    payments.confirm_payment(payment.pk)
    successor = service.renegotiate_billing(billing.pk, new_due_date=timezone.localdate())[0]
    return billing, payment, successor


@pytest.mark.parametrize(
    "fee,interest,amount", [("0", "0", "40"), ("5", "3", "4"), ("5", "3", "7"), ("5", "3", "40")]
)
def test_reverse_renegotiation_restores_exact_components(user, fee, interest, amount):
    billing, payment, successor = _renegotiated_payment(
        user, fee=fee, interest=interest, amount=amount
    )
    billing.refresh_from_db()
    before = successor.principal_value
    allocation = payment.allocations.get()
    PaymentService(user=user).reverse_payment(
        payment.pk, reason="Reversal", adjustment_due_date=timezone.localdate()
    )
    adjustment = BillingEntry.objects.get(reversal_allocation=allocation)
    assert (adjustment.principal_value, adjustment.late_fee_value, adjustment.interest_value) == (
        allocation.principal_amount,
        allocation.late_fee_amount,
        allocation.interest_amount,
    )
    assert adjustment.competency == billing.competency
    assert adjustment.contract_id is None and adjustment.installment_number is None
    assert adjustment.late_fee_percent == adjustment.daily_interest_percent == 0
    assert adjustment.outstanding_value + successor.outstanding_value == Decimal("100") + Decimal(
        fee
    ) + Decimal(interest)
    billing.refresh_from_db()
    successor.refresh_from_db()
    assert billing.paid_value == 0 and billing.status == "CANCELLED"
    assert successor.principal_value == before
    with pytest.raises(BusinessRuleViolationError):
        PaymentService(user=user).reverse_payment(
            payment.pk, reason="Retry", adjustment_due_date=timezone.localdate()
        )
    assert BillingEntry.objects.filter(reversal_allocation=allocation).count() == 1


@pytest.mark.parametrize("invalid_date", [None, dt.date(2000, 1, 1)])
def test_reverse_renegotiation_requires_current_or_future_due_date(user, invalid_date):
    _, payment, _ = _renegotiated_payment(user)
    with pytest.raises(ValidationError):
        PaymentService(user=user).reverse_payment(
            payment.pk, reason="Reversal", adjustment_due_date=invalid_date
        )
    payment.refresh_from_db()
    assert payment.status == PaymentRecord.Status.CONFIRMED
    assert not BillingEntry.objects.filter(reversal_allocation__isnull=False).exists()


def test_reverse_recomposition_rolls_back_when_audit_fails(user):
    _, payment, _ = _renegotiated_payment(user)
    with patch.object(
        PaymentService, "_record_audit", side_effect=RuntimeError("audit unavailable")
    ):
        with pytest.raises(RuntimeError):
            PaymentService(user=user).reverse_payment(
                payment.pk, reason="Reversal", adjustment_due_date=timezone.localdate()
            )
    payment.refresh_from_db()
    assert payment.status == "CONFIRMED"
    assert not BillingEntry.objects.filter(reversal_allocation__isnull=False).exists()


def test_renegotiate_ad_hoc_preserves_null_number(user):
    billing, _, successor = _renegotiated_payment(user)
    assert successor.contract_id is None
    assert successor.installment_number is None
    assert successor.renegotiated_from_id == billing.pk


@freeze_time("2026-01-01")
def test_amendment_reexpands_only_titles_suppressed_by_amendment(user):
    service = FinanceService(user=user)
    contract = _contract(user, _student(user))
    manually_cancelled = contract.billings.get(installment_number=12)
    service.cancel_billing(manually_cancelled.pk, "Manual")
    for count in (10, 12):
        service.create_amendment(
            contract.pk,
            {
                "effective_competency": dt.date(2026, 7, 1),
                "reason": "Calendar",
                "installment_count": count,
            },
        )
    assert contract.billings.filter(installment_number=11, status="ACTIVE").count() == 1
    assert not contract.billings.filter(installment_number=12, status="ACTIVE").exists()


def test_reverse_preserves_paid_successors_and_renegotiation_chain(user):
    original, payment, successor = _renegotiated_payment(user)
    leaf = FinanceService(user=user).renegotiate_billing(
        successor.pk, new_due_date=timezone.localdate()
    )[0]
    payments = PaymentService(user=user)
    last_payment = payments.create_payment(
        allocations=[{"billing_id": leaf.pk, "amount": leaf.outstanding_value}],
        paid_date=timezone.localdate(),
    )
    payments.confirm_payment(last_payment.pk)
    payments.reverse_payment(
        payment.pk, reason="Reversal", adjustment_due_date=timezone.localdate()
    )
    leaf.refresh_from_db()
    assert leaf.is_settled
    original.refresh_from_db()
    assert original.paid_value == 0
    assert BillingEntry.objects.get(reversal_allocation__payment=payment).outstanding_value == 40


def test_reverse_refuses_cancelled_without_successor(user):
    original, payment, _ = _renegotiated_payment(user)
    BillingEntry.all_objects.filter(renegotiated_from=original).update(renegotiated_from=None)
    with pytest.raises(BusinessRuleViolationError):
        PaymentService(user=user).reverse_payment(
            payment.pk, reason="Reversal", adjustment_due_date=timezone.localdate()
        )
    payment.refresh_from_db()
    assert payment.status == "CONFIRMED"


def test_statement_pdf_excludes_cancelled_balances_and_reversed_paid(user):
    from io import BytesIO

    from pypdf import PdfReader

    from financeiro.pdf_documents import render_student_statement

    original, payment, _ = _renegotiated_payment(user)
    PaymentService(user=user).reverse_payment(
        payment.pk, reason="Reversal", adjustment_due_date=timezone.localdate()
    )
    pdf = render_student_statement(
        original.student, BillingEntry.objects.filter(student=original.student)
    )
    text = "".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
    assert "Cancelada" in text
    assert "Totais" in text
    assert "R$ 200,00" not in text
    assert "R$ 100,00" in text


@freeze_time("2026-01-01")
def test_materialize_refuses_historical_gap_with_current_terms(user):
    service = FinanceService(user=user)
    contract = _contract(user, _student(user))
    service.create_amendment(
        contract.pk,
        {"effective_competency": dt.date(2026, 7, 1), "reason": "Terms", "installment_value": 120},
    )
    # Simula corrupção de agenda sem exclusão física de registro de domínio.
    BillingEntry.all_objects.filter(contract=contract, installment_number=1).update(
        installment_number=60
    )
    with pytest.raises(BusinessRuleViolationError):
        service.materialize_contract_billings(contract.pk)
    assert not contract.billings.filter(installment_number=1).exists()


def test_reverse_distributed_payment_recomposes_only_renegotiated_allocation(user):
    student = _student(user)
    service = FinanceService(user=user)
    original, active = [
        service.create_ad_hoc_billing(
            {
                "student_id": student.pk,
                "description": str(index),
                "amount": 100,
                "due_date": timezone.localdate(),
            }
        )
        for index in range(2)
    ]
    payments = PaymentService(user=user)
    payment = payments.create_payment(
        allocations=[
            {"billing_id": original.pk, "amount": 40},
            {"billing_id": active.pk, "amount": 30},
        ],
        paid_date=timezone.localdate(),
    )
    payments.confirm_payment(payment.pk)
    service.renegotiate_billing(original.pk, new_due_date=timezone.localdate())
    payments.reverse_payment(
        payment.pk, reason="Distributed", adjustment_due_date=timezone.localdate()
    )
    active.refresh_from_db()
    original.refresh_from_db()
    assert active.paid_value == original.paid_value == 0
    assert active.outstanding_value == 100
    assert BillingEntry.objects.filter(reversal_allocation__payment=payment).count() == 1


@pytest.mark.parametrize("offset", [-1, 7])
def test_reverse_http_validates_and_preserves_adjustment_due_date(client, user, offset):
    from django.urls import reverse

    _, payment, _ = _renegotiated_payment(user)
    client.force_login(user)
    due_date = timezone.localdate() + dt.timedelta(days=offset)
    response = client.post(
        reverse("payment_reverse", args=[payment.pk]),
        {
            "reason": "Review",
            "adjustment_due_date": due_date.isoformat(),
        },
    )
    payment.refresh_from_db()
    if offset < 0:
        assert response.status_code == 200
        assert payment.status == "CONFIRMED"
        assert response.context["form"].errors["adjustment_due_date"]
        assert not BillingEntry.objects.filter(reversal_allocation__payment=payment).exists()
    else:
        assert response.status_code == 302
        assert payment.status == "REVERSED"
        assert BillingEntry.objects.get(reversal_allocation__payment=payment).due_date == due_date
