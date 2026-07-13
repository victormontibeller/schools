"""Testes dos serviços do módulo Financeiro Escolar."""

import datetime as dt
from decimal import Decimal

import pytest

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from classes.models import Class
from financeiro.models import BillingEntry, FinancialPlan, PaymentRecord
from financeiro.selectors import BillingSelector
from financeiro.services import FinanceService, PaymentService
from students.models import Student


def _make_student(user, enrollment_number="FIN-001"):
    return Student.objects.create(
        first_name="Maria",
        last_name="Financeira",
        birth_date=dt.date(2010, 5, 15),
        enrollment_number=enrollment_number,
        created_by=user,
        updated_by=user,
    )


def _make_class(user, name="FIN-A"):
    return Class.objects.create(
        name=name,
        grade=Class.Grade.ELEMENTARY_1,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=2026,
        max_students=30,
        created_by=user,
        updated_by=user,
    )


def _plan_data(student, class_obj=None, **overrides):
    data = {
        "student_id": student.pk,
        "class_obj_id": class_obj.pk if class_obj else None,
        "academic_year": 2026,
        "name": "Mensalidade 2026",
        "billing_frequency": FinancialPlan.BillingFrequency.MONTHLY,
        "installment_count": 2,
        "installment_value": Decimal("100.00"),
        "due_day": 10,
        "discount_value": Decimal("0.00"),
        "late_fee_percent": Decimal("2.00"),
        "daily_interest_percent": Decimal("0.1000"),
    }
    data.update(overrides)
    return data


def _active_plan(user, student=None, class_obj=None, **overrides):
    student = student or _make_student(user)
    plan = FinanceService(user=user).create_plan(_plan_data(student, class_obj, **overrides))
    return FinanceService(user=user).activate_plan(plan.pk)


@pytest.mark.django_db
class TestFinancePlan:
    def test_create_plan_succeeds_with_valid_data(self, user):
        student = _make_student(user)

        plan = FinanceService(user=user).create_plan(_plan_data(student))

        assert plan.pk is not None
        assert plan.status == FinancialPlan.Status.DRAFT
        assert plan.student == student

    def test_create_plan_fails_when_student_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            FinanceService(user=user).create_plan(
                _plan_data(student=type("S", (), {"pk": uuid.uuid4()})())
            )

    def test_create_plan_fails_with_invalid_due_day(self, user):
        student = _make_student(user)

        with pytest.raises(ValidationError) as exc_info:
            FinanceService(user=user).create_plan(_plan_data(student, due_day=31))

        assert "due_day" in exc_info.value.errors

    def test_activate_plan_changes_status(self, user):
        student = _make_student(user)
        plan = FinanceService(user=user).create_plan(_plan_data(student))

        activated = FinanceService(user=user).activate_plan(plan.pk)

        assert activated.status == FinancialPlan.Status.ACTIVE

    def test_activate_plan_fails_when_not_draft(self, user):
        plan = _active_plan(user)

        with pytest.raises(BusinessRuleViolationError):
            FinanceService(user=user).activate_plan(plan.pk)

    def test_create_plan_succeeds_after_previous_plan_is_suspended(self, user):
        student = _make_student(user)
        plan = _active_plan(user, student=student)
        FinanceService(user=user).cancel_plan(plan.pk, "Mudanca de politica")

        new_plan = FinanceService(user=user).create_plan(
            _plan_data(student, name="Mensalidade revisada")
        )

        assert new_plan.pk is not None
        assert new_plan.status == FinancialPlan.Status.DRAFT


@pytest.mark.django_db
class TestBillingGeneration:
    def test_generate_billings_creates_installments(self, user):
        plan = _active_plan(user)

        created = FinanceService(user=user).generate_billings(plan.pk)

        assert created == 2
        billings = list(BillingEntry.objects.filter(plan=plan).order_by("installment_number"))
        assert [b.installment_number for b in billings] == [1, 2]
        assert billings[0].due_date == dt.date(2026, 1, 10)

    def test_generate_billings_fails_when_plan_not_active(self, user):
        student = _make_student(user)
        plan = FinanceService(user=user).create_plan(_plan_data(student))

        with pytest.raises(BusinessRuleViolationError):
            FinanceService(user=user).generate_billings(plan.pk)

    def test_generate_billings_by_class_creates_competence_for_active_plans(self, user):
        class_obj = _make_class(user)
        student = _make_student(user)
        _active_plan(user, student=student, class_obj=class_obj)

        created = FinanceService(user=user).generate_billings_by_class(
            class_obj.pk,
            2026,
            month=2,
        )

        billing = BillingEntry.objects.get(student=student)
        assert created == 1
        assert billing.installment_number == 2
        assert billing.due_date == dt.date(2026, 2, 10)

    def test_refresh_overdue_status_marks_open_billings(self, user):
        plan = _active_plan(user)
        FinanceService(user=user).generate_billings(plan.pk)

        count = FinanceService(user=user).refresh_overdue_status(
            reference_date=dt.date(2026, 1, 11)
        )

        assert count == 1
        assert (
            BillingEntry.objects.get(plan=plan, installment_number=1).status
            == BillingEntry.Status.OVERDUE
        )


@pytest.mark.django_db
class TestPayments:
    def test_register_payment_accepts_partial_and_total_payment(self, user):
        plan = _active_plan(user)
        FinanceService(user=user).generate_billings(plan.pk)
        billing = BillingEntry.objects.get(plan=plan, installment_number=1)
        billing.due_date = dt.date(2026, 12, 10)
        billing.save(update_fields=["due_date", "updated_at"])

        PaymentService(user=user).register_payment(
            billing.pk,
            amount=Decimal("40.00"),
            paid_date=dt.date(2026, 7, 8),
            payment_method=PaymentRecord.PaymentMethod.PIX,
        )
        billing.refresh_from_db()
        assert billing.paid_value == Decimal("40.00")
        assert billing.status == BillingEntry.Status.OPEN

        PaymentService(user=user).register_payment(
            billing.pk,
            amount=Decimal("60.00"),
            paid_date=dt.date(2026, 7, 8),
            payment_method=PaymentRecord.PaymentMethod.PIX,
        )
        billing.refresh_from_db()
        assert billing.paid_value == Decimal("100.00")
        assert billing.status == BillingEntry.Status.PAID

    def test_register_payment_fails_when_amount_exceeds_balance(self, user):
        plan = _active_plan(user)
        FinanceService(user=user).generate_billings(plan.pk)
        billing = BillingEntry.objects.get(plan=plan, installment_number=1)

        with pytest.raises(ValidationError) as exc_info:
            PaymentService(user=user).register_payment(
                billing.pk,
                amount=Decimal("101.00"),
                paid_date=dt.date(2026, 1, 9),
            )

        assert "amount" in exc_info.value.errors

    def test_register_partial_backdated_payment_keeps_overdue_status(self, user):
        plan = _active_plan(user)
        FinanceService(user=user).generate_billings(plan.pk)
        billing = BillingEntry.objects.get(plan=plan, installment_number=1)
        billing.due_date = dt.date(2026, 1, 1)
        billing.save(update_fields=["due_date", "updated_at"])

        PaymentService(user=user).register_payment(
            billing.pk,
            amount=Decimal("40.00"),
            paid_date=dt.date(2026, 1, 1),
        )

        billing.refresh_from_db()
        assert billing.status == BillingEntry.Status.OVERDUE

    def test_reconcile_confirm_marks_payment_as_confirmed(self, user):
        plan = _active_plan(user)
        FinanceService(user=user).generate_billings(plan.pk)
        billing = BillingEntry.objects.get(plan=plan, installment_number=1)
        payment = PaymentService(user=user).register_payment(
            billing.pk,
            amount=Decimal("100.00"),
            paid_date=dt.date(2026, 1, 9),
        )

        reconciled = PaymentService(user=user).reconcile(payment.pk, confirmed=True)

        assert reconciled.reconciliation_status == PaymentRecord.ReconciliationStatus.CONFIRMED
        assert reconciled.reconciled_at is not None

    def test_reconcile_rejected_soft_deletes_payment_and_restores_balance(self, user):
        plan = _active_plan(user)
        FinanceService(user=user).generate_billings(plan.pk)
        billing = BillingEntry.objects.get(plan=plan, installment_number=1)
        payment = PaymentService(user=user).register_payment(
            billing.pk,
            amount=Decimal("100.00"),
            paid_date=dt.date(2026, 1, 9),
        )

        PaymentService(user=user).reconcile(payment.pk, confirmed=False)

        billing.refresh_from_db()
        payment = PaymentRecord.all_objects.get(pk=payment.pk)
        assert billing.paid_value == Decimal("0.00")
        assert billing.status == BillingEntry.Status.OVERDUE
        assert payment.deleted_at is not None
        assert payment.reconciliation_status == PaymentRecord.ReconciliationStatus.REJECTED


@pytest.mark.django_db
class TestBillingPolicies:
    def test_apply_late_fees_adds_fee_and_interest_once(self, user):
        plan = _active_plan(user, installment_count=1)
        FinanceService(user=user).generate_billings(plan.pk)
        billing = BillingEntry.objects.get(plan=plan)
        billing.status = BillingEntry.Status.OVERDUE
        billing.due_date = dt.date(2026, 1, 1)
        billing.save(update_fields=["status", "due_date", "updated_at"])

        updated = FinanceService(user=user).apply_late_fees(
            billing.pk,
            reference_date=dt.date(2026, 1, 11),
        )
        second = FinanceService(user=user).apply_late_fees(
            billing.pk,
            reference_date=dt.date(2026, 1, 11),
        )

        assert updated.original_value == Decimal("103.00")
        assert second.original_value == Decimal("103.00")
        assert "[multa-aplicada]" in second.notes

    def test_renegotiate_billing_cancels_original_and_creates_new_installments(self, user):
        plan = _active_plan(user)
        FinanceService(user=user).generate_billings(plan.pk)
        billing = BillingEntry.objects.get(plan=plan, installment_number=1)

        new_billings = FinanceService(user=user).renegotiate_billing(
            billing.pk,
            new_due_date=dt.date(2026, 3, 10),
            installment_count=2,
        )

        billing.refresh_from_db()
        assert billing.status == BillingEntry.Status.CANCELLED
        assert [b.installment_number for b in new_billings] == [3, 4]
        assert [b.original_value for b in new_billings] == [Decimal("50.00"), Decimal("50.00")]

    def test_renegotiate_billing_preserves_total_when_split_has_remainder(self, user):
        plan = _active_plan(user)
        FinanceService(user=user).generate_billings(plan.pk)
        billing = BillingEntry.objects.get(plan=plan, installment_number=1)

        new_billings = FinanceService(user=user).renegotiate_billing(
            billing.pk,
            new_due_date=dt.date(2026, 3, 10),
            new_value=Decimal("100.00"),
            installment_count=3,
        )

        assert sum((item.original_value for item in new_billings), Decimal("0.00")) == Decimal(
            "100.00"
        )
        assert [item.original_value for item in new_billings] == [
            Decimal("33.33"),
            Decimal("33.33"),
            Decimal("33.34"),
        ]


@pytest.mark.django_db
class TestFinancialSelectors:
    def test_finance_kpis_consider_open_billing_overdue_by_due_date(self, user):
        plan = _active_plan(user, installment_count=1)
        FinanceService(user=user).generate_billings(plan.pk)
        billing = BillingEntry.objects.get(plan=plan, installment_number=1)
        billing.due_date = dt.date(2026, 1, 1)
        billing.status = BillingEntry.Status.OPEN
        billing.save(update_fields=["due_date", "status", "updated_at"])

        kpis = BillingSelector().finance_kpis(reference_date=dt.date(2026, 1, 11))
        bands = BillingSelector().inadimplencia_por_faixa(reference_date=dt.date(2026, 1, 11))

        assert kpis["total_vencido"] == Decimal("100.00")
        assert kpis["total_aberto"] == Decimal("0.00")
        assert bands[0]["quantidade"] == 1
