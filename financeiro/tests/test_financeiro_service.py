"""Testes dos serviços do módulo Financeiro Escolar."""

import datetime as dt
import uuid
from decimal import Decimal

import pytest

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from classes.models import Class
from financeiro.models import BillingEntry, PaymentRecord, StudentFinancialContract
from financeiro.selectors import BillingSelector
from financeiro.services import FinanceService, PaymentService
from students.models import Student


def _create_single_payment(service, billing_id, *, amount, **kwargs):
    return service.create_payment(
        allocations=[{"billing_id": billing_id, "amount": amount}],
        **kwargs,
    )


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


def _contract_data(student, class_obj=None, **overrides):
    data = {
        "student_id": student.pk,
        "class_obj_id": class_obj.pk if class_obj else None,
        "academic_year": 2026,
        "name": "Mensalidade 2026",
        "billing_frequency": StudentFinancialContract.BillingFrequency.MONTHLY,
        "installment_count": 2,
        "installment_value": Decimal("100.00"),
        "due_day": 10,
        "discount_value": Decimal("0.00"),
        "late_fee_percent": Decimal("2.00"),
        "daily_interest_percent": Decimal("0.1000"),
    }
    data.update(overrides)
    return data


def _active_contract(user, student=None, class_obj=None, **overrides):
    student = student or _make_student(user)
    contract = FinanceService(user=user).create_contract(
        _contract_data(student, class_obj, **overrides)
    )
    return FinanceService(user=user).activate_contract(contract.pk)


@pytest.mark.django_db
class TestFinancialContract:
    def test_create_contract_succeeds_with_valid_data(self, user):
        student = _make_student(user)

        contract = FinanceService(user=user).create_contract(_contract_data(student))

        assert contract.pk is not None
        assert contract.status == StudentFinancialContract.Status.DRAFT
        assert contract.student == student

    def test_create_contract_fails_when_student_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            FinanceService(user=user).create_contract(
                _contract_data(student=type("S", (), {"pk": uuid.uuid4()})())
            )

    def test_create_contract_fails_with_invalid_due_day(self, user):
        student = _make_student(user)

        with pytest.raises(ValidationError) as exc_info:
            FinanceService(user=user).create_contract(_contract_data(student, due_day=31))

        assert "due_day" in exc_info.value.errors

    def test_activate_contract_changes_status(self, user):
        student = _make_student(user)
        contract = FinanceService(user=user).create_contract(_contract_data(student))

        activated = FinanceService(user=user).activate_contract(contract.pk)

        assert activated.status == StudentFinancialContract.Status.ACTIVE
        assert BillingEntry.objects.filter(contract=activated).count() == 2

    def test_activate_contract_fails_when_not_draft(self, user):
        contract = _active_contract(user)

        with pytest.raises(BusinessRuleViolationError):
            FinanceService(user=user).activate_contract(contract.pk)

    def test_create_contract_rejects_second_current_contract_when_previous_is_suspended(self, user):
        student = _make_student(user)
        contract = _active_contract(user, student=student)
        FinanceService(user=user).suspend_contract(contract.pk, "Mudanca de politica")

        with pytest.raises(BusinessRuleViolationError):
            FinanceService(user=user).create_contract(
                _contract_data(student, name="Mensalidade revisada")
            )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("installment_count", 0),
            ("installment_count", 61),
            ("installment_value", 0),
            ("discount_value", -1),
        ],
    )
    def test_create_contract_rejects_invalid_financial_values(self, user, field, value):
        student = _make_student(user, enrollment_number=f"FIN-{field}-{value}")

        with pytest.raises(ValidationError):
            FinanceService(user=user).create_contract(_contract_data(student, **{field: value}))

    def test_create_contract_rejects_missing_class_and_duplicate_draft(self, user):
        student = _make_student(user, enrollment_number="FIN-DUPLICATE")
        FinanceService(user=user).create_contract(_contract_data(student))

        with pytest.raises(BusinessRuleViolationError):
            FinanceService(user=user).create_contract(_contract_data(student, name="Duplicado"))
        with pytest.raises(ObjectNotFoundError):
            FinanceService(user=user).create_contract(
                _contract_data(
                    _make_student(user, enrollment_number="FIN-MISSING-CLASS"),
                    class_obj=type("ClassRef", (), {"pk": uuid.uuid4()})(),
                )
            )


@pytest.mark.django_db
class TestBillingGeneration:
    def test_materialize_billings_creates_installments(self, user):
        contract = _active_contract(user)

        created = FinanceService(user=user).materialize_contract_billings(contract.pk)

        assert created == 0
        billings = list(
            BillingEntry.objects.filter(contract=contract).order_by("installment_number")
        )
        assert [b.installment_number for b in billings] == [1, 2]
        assert billings[0].due_date == dt.date(2026, 1, 10)

    def test_materialize_billings_fails_when_contract_not_active(self, user):
        student = _make_student(user)
        contract = FinanceService(user=user).create_contract(_contract_data(student))

        with pytest.raises(BusinessRuleViolationError):
            FinanceService(user=user).materialize_contract_billings(contract.pk)

    def test_materialize_billings_by_class_creates_competence_for_active_contracts(self, user):
        class_obj = _make_class(user)
        student = _make_student(user)
        _active_contract(user, student=student, class_obj=class_obj)

        created = FinanceService(user=user).materialize_billings_by_class(
            class_obj.pk,
            2026,
            month=2,
        )

        billing = BillingEntry.objects.get(student=student, installment_number=2)
        assert created == 0
        assert billing.installment_number == 2
        assert billing.due_date == dt.date(2026, 2, 10)

    def test_due_state_is_derived_without_status_write(self, user):
        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        assert billing.status == BillingEntry.Status.ACTIVE
        assert billing.due_status(reference_date=dt.date(2026, 1, 11)) == "OVERDUE"

    def test_materialize_billings_is_idempotent_and_rejects_zero_net_value(self, user):
        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        assert FinanceService(user=user).materialize_contract_billings(contract.pk) == 0

        with pytest.raises(ValidationError):
            _active_contract(
                user,
                student=_make_student(user, enrollment_number="FIN-ZERO-NET"),
                installment_value=Decimal("100.00"),
                discount_value=Decimal("100.00"),
            )

    def test_materialize_billings_by_class_rejects_missing_class(self, user):
        with pytest.raises(ObjectNotFoundError):
            FinanceService(user=user).materialize_billings_by_class(uuid.uuid4(), 2026)


@pytest.mark.django_db
class TestPayments:
    def test_create_payment_accepts_partial_and_total_payment(self, user):
        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        billing.due_date = dt.date(2026, 12, 10)
        billing.save(update_fields=["due_date", "updated_at"])

        first = _create_single_payment(
            PaymentService(user=user),
            billing.pk,
            amount=Decimal("40.00"),
            paid_date=dt.date(2026, 7, 8),
            payment_method=PaymentRecord.PaymentMethod.PIX,
        )
        billing.refresh_from_db()
        assert billing.paid_value == Decimal("0.00")
        PaymentService(user=user).confirm_payment(first.pk)
        billing.refresh_from_db()
        assert billing.paid_value == Decimal("40.00")
        assert billing.status == BillingEntry.Status.ACTIVE

        second = _create_single_payment(
            PaymentService(user=user),
            billing.pk,
            amount=Decimal("60.00"),
            paid_date=dt.date(2026, 7, 8),
            payment_method=PaymentRecord.PaymentMethod.PIX,
        )
        PaymentService(user=user).confirm_payment(second.pk)
        billing.refresh_from_db()
        assert billing.paid_value == Decimal("100.00")
        assert billing.status == BillingEntry.Status.ACTIVE
        assert billing.settlement_status == "PAID"

    def test_create_payment_fails_when_amount_exceeds_balance(self, user):
        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)

        with pytest.raises(ValidationError) as exc_info:
            _create_single_payment(
                PaymentService(user=user),
                billing.pk,
                amount=Decimal("101.00"),
                paid_date=dt.date(2026, 1, 9),
            )

        assert "allocations" in exc_info.value.errors

    def test_register_partial_backdated_payment_keeps_overdue_status(self, user):
        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        billing.due_date = dt.date(2026, 1, 1)
        billing.save(update_fields=["due_date", "updated_at"])

        payment = _create_single_payment(
            PaymentService(user=user),
            billing.pk,
            amount=Decimal("40.00"),
            paid_date=dt.date(2026, 1, 1),
        )

        PaymentService(user=user).confirm_payment(payment.pk)
        billing.refresh_from_db()
        assert billing.status == BillingEntry.Status.ACTIVE
        assert billing.due_status() == "OVERDUE"

    def test_reconcile_confirm_marks_payment_as_confirmed(self, user):
        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        payment = _create_single_payment(
            PaymentService(user=user),
            billing.pk,
            amount=Decimal("100.00"),
            paid_date=dt.date(2026, 1, 9),
        )

        reconciled = PaymentService(user=user).confirm_payment(payment.pk)

        assert reconciled.status == PaymentRecord.Status.CONFIRMED
        assert reconciled.reconciled_at is not None

    def test_reconcile_denies_actor_without_finance_edit_permission(self, user):
        from core.models import CustomUser, Role

        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        payment = _create_single_payment(
            PaymentService(user=user),
            billing.pk,
            amount=Decimal("100.00"),
            paid_date=dt.date(2026, 1, 9),
        )
        role, _ = Role.objects.get_or_create(name=Role.Name.SECRETARY)
        actor = CustomUser.objects.create_user(
            email="secretary-reconcile@test.com",
            password="Senha123",
            role=role,
        )

        with pytest.raises(PermissionDeniedError):
            PaymentService(user=actor).confirm_payment(payment.pk)

        payment.refresh_from_db()
        assert payment.status == PaymentRecord.Status.PENDING

    def test_reverse_keeps_payment_and_restores_balance(self, user):
        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        payment = _create_single_payment(
            PaymentService(user=user),
            billing.pk,
            amount=Decimal("100.00"),
            paid_date=dt.date(2026, 1, 9),
        )

        PaymentService(user=user).confirm_payment(payment.pk)
        PaymentService(user=user).reverse_payment(payment.pk, reason="Duplicidade")

        billing.refresh_from_db()
        payment = PaymentRecord.all_objects.get(pk=payment.pk)
        assert billing.paid_value == Decimal("0.00")
        assert billing.status == BillingEntry.Status.ACTIVE
        assert payment.deleted_at is None
        assert payment.status == PaymentRecord.Status.REVERSED
        assert payment.reversal_reason == "Duplicidade"

    def test_create_payment_rejects_missing_closed_zero_and_future(self, user):
        with pytest.raises(ObjectNotFoundError):
            _create_single_payment(
                PaymentService(user=user), uuid.uuid4(), amount=1, paid_date=dt.date.today()
            )

        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        billing.status = BillingEntry.Status.CANCELLED
        billing.save(update_fields=["status", "updated_at"])
        with pytest.raises(BusinessRuleViolationError):
            _create_single_payment(
                PaymentService(user=user), billing.pk, amount=1, paid_date=dt.date.today()
            )

        billing.status = BillingEntry.Status.ACTIVE
        billing.save(update_fields=["status", "updated_at"])
        with pytest.raises(ValidationError):
            _create_single_payment(
                PaymentService(user=user), billing.pk, amount=0, paid_date=dt.date.today()
            )
        with pytest.raises(ValidationError):
            _create_single_payment(
                PaymentService(user=user),
                billing.pk,
                amount=1,
                paid_date=dt.date.today() + dt.timedelta(days=1),
            )

    def test_confirm_rejects_missing_reversed_and_is_idempotent_when_confirmed(self, user):
        with pytest.raises(ObjectNotFoundError):
            PaymentService(user=user).confirm_payment(uuid.uuid4())

        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        payment = _create_single_payment(
            PaymentService(user=user),
            billing.pk,
            amount=Decimal("10.00"),
            paid_date=dt.date.today(),
        )
        payment.status = PaymentRecord.Status.REVERSED
        payment.save(update_fields=["status", "updated_at"])
        with pytest.raises(BusinessRuleViolationError):
            PaymentService(user=user).confirm_payment(payment.pk)

        payment.status = PaymentRecord.Status.CONFIRMED
        payment.save(update_fields=["status", "updated_at"])
        assert PaymentService(user=user).confirm_payment(payment.pk).pk == payment.pk


@pytest.mark.django_db
class TestBillingPolicies:
    def test_assess_late_charges_adds_fee_and_interest_once(self, user):
        contract = _active_contract(user, installment_count=1)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract)
        billing.due_date = dt.date(2026, 1, 1)
        billing.save(update_fields=["due_date", "updated_at"])

        updated = FinanceService(user=user).assess_late_charges(
            billing.pk,
            reference_date=dt.date(2026, 1, 11),
        )
        second = FinanceService(user=user).assess_late_charges(
            billing.pk,
            reference_date=dt.date(2026, 1, 11),
        )

        assert updated.principal_value == Decimal("100.00")
        assert updated.late_fee_value == Decimal("2.00")
        assert updated.interest_value == Decimal("1.00")
        assert second.net_value == Decimal("103.00")

    def test_renegotiate_billing_cancels_original_and_creates_new_installments(self, user):
        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)

        new_billings = FinanceService(user=user).renegotiate_billing(
            billing.pk,
            new_due_date=dt.date(2026, 3, 10),
            new_value=Decimal("100.00"),
            installment_count=2,
        )

        billing.refresh_from_db()
        assert billing.status == BillingEntry.Status.CANCELLED
        assert [b.installment_number for b in new_billings] == [3, 4]
        assert [b.principal_value for b in new_billings] == [Decimal("50.00"), Decimal("50.00")]

    def test_renegotiate_billing_preserves_total_when_split_has_remainder(self, user):
        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)

        new_billings = FinanceService(user=user).renegotiate_billing(
            billing.pk,
            new_due_date=dt.date(2026, 3, 10),
            new_value=Decimal("100.00"),
            installment_count=3,
        )

        assert sum((item.principal_value for item in new_billings), Decimal("0.00")) == Decimal(
            "100.00"
        )
        assert [item.principal_value for item in new_billings] == [
            Decimal("33.33"),
            Decimal("33.33"),
            Decimal("33.34"),
        ]

    def test_cancel_contract_and_billing_validate_state_and_cancel_successfully(self, user):
        student = _make_student(user, enrollment_number="FIN-CANCEL-DRAFT")
        draft = FinanceService(user=user).create_contract(_contract_data(student))
        cancelled_draft = FinanceService(user=user).cancel_contract(draft.pk)
        assert cancelled_draft.status == StudentFinancialContract.Status.CANCELLED

        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        cancelled = FinanceService(user=user).cancel_billing(billing.pk, "Solicitação")

        assert cancelled.status == BillingEntry.Status.CANCELLED
        assert cancelled.cancelled_reason == "Solicitação"
        with pytest.raises(BusinessRuleViolationError):
            FinanceService(user=user).cancel_billing(billing.pk)
        with pytest.raises(ObjectNotFoundError):
            FinanceService(user=user).cancel_billing(uuid.uuid4())

    def test_renegotiate_rejects_missing_closed_and_invalid_values(self, user):
        with pytest.raises(ObjectNotFoundError):
            FinanceService(user=user).renegotiate_billing(
                uuid.uuid4(), new_due_date=dt.date.today()
            )

        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        billing.paid_value = billing.net_value
        billing.paid_principal_value = billing.contractual_value
        billing.save(update_fields=["paid_value", "paid_principal_value", "updated_at"])
        with pytest.raises(BusinessRuleViolationError):
            FinanceService(user=user).renegotiate_billing(billing.pk, new_due_date=dt.date.today())

        billing.status = BillingEntry.Status.ACTIVE
        billing.paid_value = Decimal("0.00")
        billing.paid_principal_value = Decimal("0.00")
        billing.save(update_fields=["status", "paid_value", "paid_principal_value", "updated_at"])
        for kwargs in (
            {"new_due_date": "2026-01-01"},
            {"new_due_date": dt.date.today(), "new_value": 0},
            {"new_due_date": dt.date.today(), "installment_count": 13},
        ):
            with pytest.raises(ValidationError):
                FinanceService(user=user).renegotiate_billing(billing.pk, **kwargs)

        billing.paid_value = billing.principal_value
        billing.save(update_fields=["paid_value", "updated_at"])
        with pytest.raises(BusinessRuleViolationError):
            FinanceService(user=user).renegotiate_billing(billing.pk, new_due_date=dt.date.today())

    def test_assess_late_charges_rejects_missing_wrong_state_and_non_late_date(self, user):
        with pytest.raises(ObjectNotFoundError):
            FinanceService(user=user).assess_late_charges(uuid.uuid4())

        contract = _active_contract(user)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        billing.due_date = dt.date.today() + dt.timedelta(days=1)
        billing.save(update_fields=["due_date", "updated_at"])
        unchanged = FinanceService(user=user).assess_late_charges(billing.pk)
        assert unchanged.late_fee_value == Decimal("0.00")

        unchanged = FinanceService(user=user).assess_late_charges(
            billing.pk, reference_date=billing.due_date
        )
        assert unchanged.interest_value == Decimal("0.00")


@pytest.mark.django_db
class TestFinancialSelectors:
    def test_finance_kpis_consider_open_billing_overdue_by_due_date(self, user):
        contract = _active_contract(user, installment_count=1)
        FinanceService(user=user).materialize_contract_billings(contract.pk)
        billing = BillingEntry.objects.get(contract=contract, installment_number=1)
        billing.due_date = dt.date(2026, 1, 1)
        billing.status = BillingEntry.Status.ACTIVE
        billing.save(update_fields=["due_date", "status", "updated_at"])

        kpis = BillingSelector().finance_kpis(reference_date=dt.date(2026, 1, 11))
        bands = BillingSelector().inadimplencia_por_faixa(reference_date=dt.date(2026, 1, 11))

        assert kpis["total_vencido"] == Decimal("100.00")
        assert kpis["total_aberto"] == Decimal("0.00")
        assert bands[0]["quantidade"] == 1
