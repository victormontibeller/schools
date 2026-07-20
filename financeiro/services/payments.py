"""Registro, alocação, conciliação e estorno de pagamentos manuais."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction
from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import BaseService, service_command
from financeiro.services.rules import ZERO, FinanceRulesMixin

if TYPE_CHECKING:
    from financeiro.models import PaymentRecord


class PaymentService(FinanceRulesMixin, BaseService):
    """Mantém pagamentos pendentes sem alterar saldos antes da conciliação."""

    @service_command
    def create_payment(
        self,
        *,
        allocations: list[dict],
        paid_date: date,
        payment_method: str = "CASH",
        reference: str = "",
        notes: str = "",
        idempotency_key=None,
    ) -> PaymentRecord:
        """Registra uma baixa pendente distribuída entre cobranças selecionadas."""
        from financeiro.models import BillingEntry, PaymentAllocation, PaymentRecord

        if not allocations:
            raise ValidationError(errors={"allocations": ["Selecione ao menos uma cobrança."]})
        if not isinstance(paid_date, date) or paid_date > date.today():
            raise ValidationError(errors={"paid_date": ["A data não pode ser futura."]})
        if idempotency_key:
            existing = PaymentRecord.all_objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing

        normalized: dict[str, Decimal] = {}
        for item in allocations:
            billing_id = str(item.get("billing_id", ""))
            value = self._to_decimal(item.get("amount"))
            if not billing_id or value <= ZERO:
                raise ValidationError(errors={"allocations": ["Alocação inválida."]})
            normalized[billing_id] = normalized.get(billing_id, ZERO) + value
        billings = {
            str(item.pk): item
            for item in BillingEntry.objects.filter(pk__in=normalized).select_related("contract")
        }
        if set(billings) != set(normalized):
            missing = next(iter(set(normalized) - set(billings)))
            raise ObjectNotFoundError("BillingEntry", missing)
        for billing_id, value in normalized.items():
            billing = billings[billing_id]
            if billing.status == BillingEntry.Status.CANCELLED or billing.is_settled:
                raise BusinessRuleViolationError("Cobrança encerrada não aceita pagamento.")
            if value > billing.outstanding_value:
                raise ValidationError(
                    errors={"allocations": ["O valor excede o saldo atualmente apurado."]}
                )

        total = sum(normalized.values(), ZERO)
        create_values = {
            "amount": total,
            "paid_date": paid_date,
            "payment_method": payment_method,
            "reference": reference.strip(),
            "received_by": self.user,
            "notes": notes.strip(),
            "created_by": self.user,
            "updated_by": self.user,
        }
        if idempotency_key:
            create_values["idempotency_key"] = idempotency_key
        if idempotency_key:
            try:
                with transaction.atomic():
                    payment = PaymentRecord.objects.create(**create_values)
            except IntegrityError:
                return PaymentRecord.all_objects.get(idempotency_key=idempotency_key)
        else:
            payment = PaymentRecord.objects.create(**create_values)
        self._record_audit("INSERT", payment)
        for billing_id, value in normalized.items():
            allocation = PaymentAllocation.objects.create(
                payment=payment,
                billing=billings[billing_id],
                amount=value,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", allocation)
        self._log(
            "payment_pending_created",
            payment_id=str(payment.pk),
            allocation_count=len(normalized),
            amount=str(total),
        )
        return payment

    @service_command
    def confirm_payment(self, payment_id) -> PaymentRecord:
        """Concilia sob lock, apura encargos e só então altera saldos e caixa."""
        from financeiro.models import (
            BillingEntry,
            FinancialSequence,
            PaymentAllocation,
            PaymentRecord,
        )
        from financeiro.services import FinanceService

        try:
            payment = PaymentRecord.objects.select_for_update().get(pk=payment_id)
        except PaymentRecord.DoesNotExist:
            raise ObjectNotFoundError("PaymentRecord", str(payment_id)) from None
        if payment.status == PaymentRecord.Status.CONFIRMED:
            return payment
        if payment.status == PaymentRecord.Status.REVERSED:
            raise BusinessRuleViolationError("Pagamento estornado não pode ser conciliado.")

        allocations = list(
            PaymentAllocation.objects.select_for_update()
            .filter(payment=payment)
            .order_by("billing_id")
        )
        if not allocations:
            raise BusinessRuleViolationError("Pagamento não possui alocações.")
        billing_ids = [allocation.billing_id for allocation in allocations]
        billings = {
            billing.pk: billing
            for billing in BillingEntry.objects.select_for_update(of=("self",))
            .select_related("contract")
            .filter(pk__in=billing_ids)
            .order_by("pk")
        }
        finance_service = FinanceService(user=self.user)
        for allocation in allocations:
            billing = billings[allocation.billing_id]
            finance_service._assess_late_charges(billing, payment.paid_date)
            billing.refresh_from_db()
            if billing.status == BillingEntry.Status.CANCELLED:
                raise BusinessRuleViolationError("Uma cobrança selecionada foi cancelada.")
            if allocation.amount > billing.outstanding_value:
                raise BusinessRuleViolationError(
                    "O saldo mudou após o registro. Revise a baixa antes de conciliar."
                )
            remaining = allocation.amount
            unpaid_fee = max(billing.late_fee_value - billing.paid_late_fee_value, ZERO)
            allocation.late_fee_amount = min(remaining, unpaid_fee)
            remaining -= allocation.late_fee_amount
            unpaid_interest = max(billing.interest_value - billing.paid_interest_value, ZERO)
            allocation.interest_amount = min(remaining, unpaid_interest)
            remaining -= allocation.interest_amount
            unpaid_principal = max(
                billing.contractual_value - billing.paid_principal_value,
                ZERO,
            )
            allocation.principal_amount = min(remaining, unpaid_principal)
            remaining -= allocation.principal_amount
            if remaining != ZERO:
                raise BusinessRuleViolationError("A alocação excede os componentes da cobrança.")
            allocation.updated_by = self.user
            allocation.save()
            self._record_audit("UPDATE", allocation)

            old = {
                "paid_value": str(billing.paid_value),
                "status": billing.status,
            }
            billing.paid_late_fee_value += allocation.late_fee_amount
            billing.paid_interest_value += allocation.interest_amount
            billing.paid_principal_value += allocation.principal_amount
            billing.paid_value += allocation.amount
            billing.updated_by = self.user
            billing.save()
            self._record_audit("UPDATE", billing, old_values=old)

        sequence_created = False
        try:
            sequence = FinancialSequence.objects.select_for_update().get(
                kind="RECEIPT", year=payment.paid_date.year
            )
        except FinancialSequence.DoesNotExist:
            try:
                with transaction.atomic():
                    sequence = FinancialSequence.objects.create(
                        kind="RECEIPT",
                        year=payment.paid_date.year,
                        created_by=self.user,
                        updated_by=self.user,
                    )
                    sequence_created = True
            except IntegrityError:
                pass
            sequence = FinancialSequence.objects.select_for_update().get(
                kind="RECEIPT", year=payment.paid_date.year
            )
        old_sequence_value = sequence.last_value
        sequence.last_value += 1
        sequence.updated_by = self.user
        sequence.save()
        self._record_audit(
            "INSERT" if sequence_created else "UPDATE",
            sequence,
            old_values={} if sequence_created else {"last_value": old_sequence_value},
        )
        payment.receipt_number = f"REC-{payment.paid_date.year}-{sequence.last_value:06d}"
        payment.status = PaymentRecord.Status.CONFIRMED
        payment.reconciled_at = timezone.now()
        payment.confirmed_by = self.user
        payment.updated_by = self.user
        payment.save()
        self._record_audit("UPDATE", payment, old_values={"status": "PENDING"})
        self._log(
            "payment_confirmed",
            payment_id=str(payment.pk),
            allocation_count=len(allocations),
            receipt_number=payment.receipt_number,
        )
        return payment

    @service_command
    def reverse_payment(self, payment_id, *, reason: str) -> PaymentRecord:
        """Estorna componentes confirmados sem excluir o registro financeiro."""
        from financeiro.models import BillingEntry, PaymentAllocation, PaymentRecord

        if not reason.strip():
            raise ValidationError(errors={"reason": ["Informe o motivo do estorno."]})
        try:
            payment = PaymentRecord.objects.select_for_update().get(pk=payment_id)
        except PaymentRecord.DoesNotExist:
            raise ObjectNotFoundError("PaymentRecord", str(payment_id)) from None
        if payment.status != PaymentRecord.Status.CONFIRMED:
            raise BusinessRuleViolationError("Somente pagamento conciliado pode ser estornado.")
        allocations = list(
            PaymentAllocation.objects.select_for_update()
            .filter(payment=payment)
            .order_by("billing_id")
        )
        billings = {
            item.pk: item
            for item in BillingEntry.objects.select_for_update().filter(
                pk__in=[allocation.billing_id for allocation in allocations]
            )
        }
        for allocation in allocations:
            billing = billings[allocation.billing_id]
            old = {"paid_value": str(billing.paid_value), "status": billing.status}
            billing.paid_late_fee_value = max(
                billing.paid_late_fee_value - allocation.late_fee_amount, ZERO
            )
            billing.paid_interest_value = max(
                billing.paid_interest_value - allocation.interest_amount, ZERO
            )
            billing.paid_principal_value = max(
                billing.paid_principal_value - allocation.principal_amount, ZERO
            )
            billing.paid_value = max(billing.paid_value - allocation.amount, ZERO)
            billing.updated_by = self.user
            billing.save()
            self._record_audit("UPDATE", billing, old_values=old)
        payment.status = PaymentRecord.Status.REVERSED
        payment.reversed_at = timezone.now()
        payment.reversed_by = self.user
        payment.reversal_reason = reason.strip()
        payment.updated_by = self.user
        payment.save()
        self._record_audit("UPDATE", payment, old_values={"status": "CONFIRMED"})
        self._log("payment_reversed", payment_id=str(payment.pk))
        return payment
