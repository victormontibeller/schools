"""Cronologia de encargos e recebimentos históricos do piloto."""

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from base.exceptions import BusinessRuleViolationError
from financeiro.models import PaymentRecord
from financeiro.selectors import BillingSelector
from financeiro.services import FinanceService, PaymentService
from financeiro.tests.test_receivables_v2 import _contract, _student
from financeiro.tests.test_stabilization import _renegotiated_payment

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("paid_date", [dt.date(2026, 1, 9), dt.date(2026, 1, 10)])
@pytest.mark.parametrize("amount", ["40", "100"])
def test_first_payment_uses_effective_date_before_assessed_charges(user, paid_date, amount):
    contract = _contract(user, _student(user), installment_count=1)
    billing = contract.billings.get()
    FinanceService(user=user).assess_late_charges(billing.pk, reference_date=dt.date(2026, 1, 15))
    payment = PaymentService(user=user).create_payment(
        allocations=[{"billing_id": billing.pk, "amount": amount}],
        paid_date=paid_date,
    )
    PaymentService(user=user).confirm_payment(payment.pk)
    billing.refresh_from_db()
    allocation = payment.allocations.get()
    assert billing.late_fee_value == billing.interest_value == 0
    assert allocation.principal_amount == Decimal(amount)
    assert billing.outstanding_value == Decimal("100") - Decimal(amount)


def test_first_late_payment_recalculates_only_to_effective_date_and_preserves_history(user):
    contract = _contract(user, _student(user), installment_count=1)
    billing = contract.billings.get()
    finance = FinanceService(user=user)
    finance.assess_late_charges(billing.pk, reference_date=dt.date(2026, 1, 15))
    service = PaymentService(user=user)
    payment = service.create_payment(
        allocations=[{"billing_id": billing.pk, "amount": "40"}], paid_date=dt.date(2026, 1, 12)
    )
    service.confirm_payment(payment.pk)
    billing.refresh_from_db()
    assert billing.interest_calculated_until == dt.date(2026, 1, 12)
    assert billing.interest_value == (
        billing.contractual_value * billing.daily_interest_percent * 2 / 100
    ).quantize(Decimal("0.01"))
    old = (billing.late_fee_value, billing.interest_value, billing.paid_value)
    earlier = service.create_payment(
        allocations=[{"billing_id": billing.pk, "amount": "10"}], paid_date=dt.date(2026, 1, 10)
    )
    with pytest.raises(BusinessRuleViolationError):
        service.confirm_payment(earlier.pk)
    billing.refresh_from_db()
    assert (billing.late_fee_value, billing.interest_value, billing.paid_value) == old


def test_first_payment_charge_reconciliation_rolls_back_when_audit_fails(user):
    from unittest.mock import patch

    contract = _contract(user, _student(user), installment_count=1)
    billing = contract.billings.get()
    FinanceService(user=user).assess_late_charges(billing.pk, reference_date=dt.date(2026, 1, 15))
    billing.refresh_from_db()
    old = (billing.late_fee_value, billing.interest_value, billing.interest_calculated_until)
    service = PaymentService(user=user)
    payment = service.create_payment(
        allocations=[{"billing_id": billing.pk, "amount": "100"}], paid_date=dt.date(2026, 1, 10)
    )
    with (
        patch.object(FinanceService, "_record_audit", side_effect=RuntimeError),
        pytest.raises(RuntimeError),
    ):
        service.confirm_payment(payment.pk)
    billing.refresh_from_db()
    assert (
        billing.late_fee_value,
        billing.interest_value,
        billing.interest_calculated_until,
    ) == old
    assert not PaymentRecord.objects.filter(status="CONFIRMED").exists()


def test_competence_preserves_renegotiated_receipts_and_reversal(user):
    billing, payment, successor = _renegotiated_payment(user)
    selector = BillingSelector(user=user)
    date = billing.competency
    report = selector.competence_report(year=date.year, month=date.month)
    assert report["received"] == Decimal("40")
    assert report["outstanding"] == Decimal("60")
    PaymentService(user=user).reverse_payment(
        payment.pk,
        reason="Correção",
        adjustment_due_date=timezone.localdate(),
    )
    report = selector.competence_report(year=date.year, month=date.month)
    assert report["received"] == 0
    assert report["outstanding"] == Decimal("100")


def test_partial_on_time_payment_leaves_due_date_base_for_future_interest(user):
    contract = _contract(user, _student(user), installment_count=1)
    billing = contract.billings.get()
    finance = FinanceService(user=user)
    finance.assess_late_charges(billing.pk, reference_date=dt.date(2026, 1, 15))
    service = PaymentService(user=user)
    payment = service.create_payment(
        allocations=[{"billing_id": billing.pk, "amount": "40"}], paid_date=dt.date(2026, 1, 9)
    )
    service.confirm_payment(payment.pk)
    finance.assess_late_charges(billing.pk, reference_date=dt.date(2026, 1, 12))
    billing.refresh_from_db()
    assert billing.interest_value == (
        Decimal("60") * billing.daily_interest_percent * 2 / 100
    ).quantize(Decimal("0.01"))


def test_excess_after_charge_reconciliation_rolls_back_and_preserves_pending(user):
    contract = _contract(user, _student(user), installment_count=1)
    billing = contract.billings.get()
    FinanceService(user=user).assess_late_charges(billing.pk, reference_date=dt.date(2026, 1, 15))
    billing.refresh_from_db()
    old = (billing.late_fee_value, billing.interest_value, billing.interest_calculated_until)
    service = PaymentService(user=user)
    payment = service.create_payment(
        allocations=[{"billing_id": billing.pk, "amount": billing.outstanding_value}],
        paid_date=dt.date(2026, 1, 10),
    )
    with pytest.raises(BusinessRuleViolationError):
        service.confirm_payment(payment.pk)
    billing.refresh_from_db()
    payment.refresh_from_db()
    assert payment.status == "PENDING"
    assert (
        billing.late_fee_value,
        billing.interest_value,
        billing.interest_calculated_until,
    ) == old
