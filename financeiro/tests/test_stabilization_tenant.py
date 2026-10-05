"""Concorrência real das invariantes financeiras por schema PostgreSQL."""

import datetime as dt
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from base import context
from base.exceptions import BusinessRuleViolationError
from core.models import CustomUser
from financeiro.models import BillingEntry
from financeiro.services import FinanceService, PaymentService
from financeiro.tests.test_receivables_v2 import _contract, _student
from tenancy.models import School

pytestmark = [pytest.mark.tenant]


@pytest.mark.skipif(os.environ.get("DJANGO_ENV") != "test_pg", reason="Requer PostgreSQL")
class TestFinancialStabilizationConcurrency(TransactionTestCase):
    """Conexões separadas disputam locks de contrato, pagamento e cobrança."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        cls.tenant = School(schema_name="financial_stabilization", name="Financial tests")
        cls.tenant.save(verbosity=0)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.tenant.delete(force_drop=True)
        super().tearDownClass()

    def setUp(self):
        connection.set_tenant(self.tenant)
        self.token = context.current_tenant.set(self.tenant.schema_name)
        self.actor = CustomUser.objects.create_user(
            email=f"{self._testMethodName}@tenant.test",
            password="Test-pass-123",
            is_superuser=True,
            is_staff=True,
        )

    def tearDown(self):
        context.current_tenant.reset(self.token)

    def _race(self, operation):
        barrier = Barrier(2)

        def run(index):
            thread_connection = connections["default"]
            thread_connection.set_tenant(self.tenant)
            token = context.current_tenant.set(self.tenant.schema_name)
            try:
                actor = CustomUser.objects.get(pk=self.actor.pk)
                barrier.wait(timeout=10)
                try:
                    return operation(actor, index)
                except BusinessRuleViolationError:
                    return "blocked"
            finally:
                context.current_tenant.reset(token)
                thread_connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(run, [0, 1]))

    def test_materialize_concurrently_creates_each_installment_once(self):
        contract = FinanceService(user=self.actor).create_contract(
            {
                "student_id": _student(self.actor, self._testMethodName[-20:]).pk,
                "academic_year": 2026,
                "name": "Concurrency",
                "installment_count": 12,
                "installment_value": 100,
                "due_day": 10,
            }
        )
        # Fixture deliberately starts with an active empty calendar.
        contract.status = "ACTIVE"
        contract.save()
        results = self._race(
            lambda actor, index: FinanceService(user=actor).materialize_contract_billings(
                contract.pk
            )
        )
        assert sorted(results) == [0, 12]
        assert BillingEntry.objects.filter(contract=contract).count() == 12

    def test_renegotiate_concurrently_serializes_contract_numbering(self):
        contract = _contract(self.actor, _student(self.actor, self._testMethodName[-20:]))
        sources = list(contract.billings.order_by("installment_number")[:2])
        results = self._race(
            lambda actor, index: FinanceService(user=actor)
            .renegotiate_billing(sources[index].pk, new_due_date=timezone.localdate())[0]
            .installment_number
        )
        assert sorted(results) == [13, 14]

    def test_reverse_concurrently_creates_one_adjustment(self):
        billing = FinanceService(user=self.actor).create_ad_hoc_billing(
            {
                "student_id": _student(self.actor, self._testMethodName[-20:]).pk,
                "description": "Concurrency",
                "amount": 100,
                "due_date": timezone.localdate(),
            }
        )
        service = PaymentService(user=self.actor)
        payment = service.create_payment(
            allocations=[{"billing_id": billing.pk, "amount": 40}], paid_date=timezone.localdate()
        )
        service.confirm_payment(payment.pk)
        FinanceService(user=self.actor).renegotiate_billing(
            billing.pk, new_due_date=timezone.localdate() + dt.timedelta(days=1)
        )
        results = self._race(
            lambda actor, index: PaymentService(user=actor)
            .reverse_payment(
                payment.pk, reason="Reversal", adjustment_due_date=timezone.localdate()
            )
            .status
        )
        assert sorted(results) == ["REVERSED", "blocked"]
        assert BillingEntry.objects.filter(reversal_allocation__payment=payment).count() == 1

    def test_amendment_and_confirmation_do_not_corrupt_future_title(self):
        from financeiro.models import PaymentRecord

        today = timezone.localdate()
        effective = FinanceService._add_months(today.replace(day=1), 1)
        contract = _contract(
            self.actor, _student(self.actor, "AMD-PAY"), start_competency=today.replace(day=1)
        )
        billing = contract.billings.get(installment_number=2)
        payment = PaymentService(user=self.actor).create_payment(
            allocations=[{"billing_id": billing.pk, "amount": 40}],
            paid_date=today,
        )

        def command(actor, index):
            if index:
                PaymentService(user=actor).confirm_payment(payment.pk)
                return "confirmed"
            FinanceService(user=actor).create_amendment(
                contract.pk,
                {
                    "effective_competency": effective,
                    "reason": "Race",
                    "installment_value": 120,
                },
            )
            return "amended"

        results = self._race(command)
        billing.refresh_from_db()
        payment.refresh_from_db()
        if "confirmed" in results:
            assert results == ["blocked", "confirmed"]
            assert billing.status == "ACTIVE" and billing.paid_value == 40
        else:
            assert results == ["amended", "blocked"]
            assert billing.status == "CANCELLED" and billing.paid_value == 0
            assert payment.status == PaymentRecord.Status.PENDING

    def test_stream_preserves_snapshot_during_payment_from_another_connection(self):
        from financeiro.tests.test_report_performance import _assert_overdue_snapshot_after_payment

        def pay(billing_id):
            def command():
                thread_connection = connections["default"]
                thread_connection.set_tenant(self.tenant)
                token = context.current_tenant.set(self.tenant.schema_name)
                try:
                    service = PaymentService(user=CustomUser.objects.get(pk=self.actor.pk))
                    payment = service.create_payment(
                        allocations=[{"billing_id": billing_id, "amount": 10}],
                        paid_date=timezone.localdate(),
                    )
                    service.confirm_payment(payment.pk)
                finally:
                    context.current_tenant.reset(token)
                    thread_connection.close()

            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(command).result(timeout=20)

        _assert_overdue_snapshot_after_payment(self.actor, self.tenant.schema_name, pay=pay)
