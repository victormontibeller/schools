"""Baixa e conciliação de pagamentos."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import BaseService
from financeiro.services.rules import ZERO, FinanceRulesMixin

if TYPE_CHECKING:
    from financeiro.models import PaymentRecord


class PaymentService(FinanceRulesMixin, BaseService):
    """Servico de baixa manual de pagamentos e conciliacao."""

    @transaction.atomic
    def register_payment(
        self,
        billing_id,
        *,
        amount,
        paid_date: date,
        payment_method="CASH",
        notes: str = "",
    ) -> PaymentRecord:
        """Registra um pagamento (parcial ou total) e recalcula o status da cobranca."""
        from financeiro.models import BillingEntry, PaymentRecord

        try:
            billing = BillingEntry.objects.select_for_update().get(pk=billing_id)
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None

        if billing.status in (BillingEntry.Status.CANCELLED, BillingEntry.Status.PAID):
            raise BusinessRuleViolationError(
                "Cobranca cancelada ou ja quitada nao pode receber pagamento."
            )

        value = self._to_decimal(amount)
        if value <= 0:
            raise ValidationError(
                errors={"amount": ["Valor do pagamento deve ser maior que zero."]}
            )

        if value > billing.outstanding_value:
            raise ValidationError(
                errors={"amount": ["Valor do pagamento excede o saldo da cobranca."]}
            )

        if self._is_future(paid_date):
            raise ValidationError(errors={"paid_date": ["Data de pagamento nao pode ser futura."]})

        payment = PaymentRecord.objects.create(
            billing=billing,
            amount=value,
            paid_date=paid_date,
            payment_method=payment_method,
            received_by=self.user,
            notes=notes.strip(),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", payment)

        billing.paid_value = (billing.paid_value or ZERO) + value
        old_status = billing.status
        new_status = billing.computed_status()
        billing.status = new_status
        billing.updated_by = self.user
        billing.save(update_fields=["paid_value", "status", "updated_by", "updated_at", "version"])
        if old_status != new_status:
            self._record_audit("UPDATE", billing, old_values={"status": old_status})

        self._log(
            "Pagamento registrado",
            billing_id=str(billing.pk),
            payment_id=str(payment.pk),
            amount=str(value),
            new_status=new_status,
        )
        return payment

    @transaction.atomic
    def reconcile(self, payment_id, *, confirmed: bool = True) -> PaymentRecord:
        """Conciliacao basica: marca/invalida um pagamento. Em caso de invalidacao,
        estorna o valor pago da cobranca e recoloca o status correto.
        """
        from financeiro.models import BillingEntry, PaymentRecord

        try:
            payment = (
                PaymentRecord.objects.select_for_update()
                .select_related("billing")
                .get(pk=payment_id)
            )
        except PaymentRecord.DoesNotExist:
            raise ObjectNotFoundError("PaymentRecord", str(payment_id)) from None

        if payment.reconciliation_status == PaymentRecord.ReconciliationStatus.REJECTED:
            raise BusinessRuleViolationError(
                "Pagamento estornado nao pode ser conciliado novamente."
            )

        if not confirmed:
            billing = BillingEntry.objects.select_for_update().get(pk=payment.billing_id)
            old_paid = billing.paid_value
            old_status = billing.status
            billing.paid_value = max((billing.paid_value or ZERO) - payment.amount, ZERO)
            billing.status = billing.computed_status()
            billing.updated_by = self.user
            billing.save(
                update_fields=["paid_value", "status", "updated_by", "updated_at", "version"]
            )
            old_payment_status = payment.reconciliation_status
            payment.reconciliation_status = PaymentRecord.ReconciliationStatus.REJECTED
            payment.updated_by = self.user
            payment.save(
                update_fields=[
                    "reconciliation_status",
                    "updated_by",
                    "updated_at",
                    "version",
                ]
            )
            payment.soft_delete(user=self.user)
            self._record_audit(
                "DELETE",
                payment,
                old_values={"reconciliation_status": old_payment_status},
            )
            if old_status != billing.status:
                self._record_audit(
                    "UPDATE",
                    billing,
                    old_values={"status": old_status, "paid_value": str(old_paid)},
                )
            self._log(
                "Pagamento estornado (conciliacao)",
                billing_id=str(billing.pk),
                payment_id=str(payment.pk),
            )
        else:
            if payment.reconciliation_status == PaymentRecord.ReconciliationStatus.CONFIRMED:
                return payment
            old_status = payment.reconciliation_status
            payment.reconciliation_status = PaymentRecord.ReconciliationStatus.CONFIRMED
            payment.reconciled_at = timezone.now()
            payment.updated_by = self.user
            payment.save(
                update_fields=[
                    "reconciliation_status",
                    "reconciled_at",
                    "updated_by",
                    "updated_at",
                    "version",
                ]
            )
            self._record_audit("UPDATE", payment, old_values={"reconciliation_status": old_status})
            self._log(
                "Pagamento conciliado",
                billing_id=str(payment.billing_id),
                payment_id=str(payment.pk),
            )
        return payment

    @staticmethod
    def _is_future(target: date) -> bool:
        return target > date.today()
