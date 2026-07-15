"""Operações sobre cobranças financeiras."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from financeiro.services.rules import ZERO

if TYPE_CHECKING:
    from financeiro.models import BillingEntry


class BillingLifecycleMixin:
    """Cancelamento, renegociação e atualização de cobranças."""

    @transaction.atomic
    def cancel_billing(self, billing_id, reason: str = "") -> BillingEntry:
        """Cancela uma cobranca em aberto. Proibe cancelar cobranca ja paga."""
        from financeiro.models import BillingEntry

        try:
            billing = BillingEntry.objects.get(pk=billing_id)
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None

        if billing.status == BillingEntry.Status.CANCELLED:
            raise BusinessRuleViolationError("Cobranca ja esta cancelada.")
        if billing.is_settled:
            raise BusinessRuleViolationError("Cobranca quitada nao pode ser cancelada.")

        old_status = billing.status
        billing.status = BillingEntry.Status.CANCELLED
        billing.cancelled_reason = reason.strip()
        billing.updated_by = self.user
        billing.save(
            update_fields=["status", "cancelled_reason", "updated_by", "updated_at", "version"]
        )
        self._record_audit("DELETE", billing, old_values={"status": old_status})
        self._log("Cobranca cancelada", billing_id=str(billing.pk))
        return billing

    @transaction.atomic
    def renegotiate_billing(
        self,
        billing_id,
        *,
        new_due_date: date,
        new_value: Decimal | None = None,
        installment_count: int = 1,
    ) -> list[BillingEntry]:
        """Renegocia uma cobranca em aberto/vencida: cancela a original e cria 1..N novas com
        novo vencimento. Se `new_value` for omitido, usa o saldo devedor atual.

        Returns:
            Lista das novas cobrancas geradas.
        """
        from financeiro.models import BillingEntry

        try:
            billing = BillingEntry.objects.select_related("plan", "student").get(pk=billing_id)
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None

        if billing.status in (BillingEntry.Status.PAID, BillingEntry.Status.CANCELLED):
            raise BusinessRuleViolationError(
                "Cobranca quitada ou cancelada nao pode ser renegociada."
            )

        if not isinstance(new_due_date, date):
            raise ValidationError(errors={"new_due_date": ["Data de vencimento invalida."]})

        outstanding = billing.outstanding_value
        if outstanding <= 0:
            raise BusinessRuleViolationError("Cobranca nao possui saldo devedor para renegociar.")

        renegotiated_value = new_value if new_value is not None else outstanding
        renegotiated_value = self._to_decimal(renegotiated_value)
        if renegotiated_value <= 0:
            raise ValidationError(
                errors={"new_value": ["Valor renegociado deve ser maior que zero."]}
            )

        if installment_count < 1 or installment_count > 12:
            raise ValidationError(
                errors={"installment_count": ["Parcelas devem ser entre 1 e 12."]}
            )

        installment_values = self._split_amount(renegotiated_value, installment_count)

        old_status = billing.status
        billing.status = BillingEntry.Status.CANCELLED
        billing.cancelled_reason = "Renegociacao"
        billing.updated_by = self.user
        billing.save(
            update_fields=["status", "cancelled_reason", "updated_by", "updated_at", "version"]
        )
        self._record_audit("DELETE", billing, old_values={"status": old_status})

        next_installment = self._next_installment_number(billing.plan_id)
        new_billings: list[BillingEntry] = []
        for i, amount in enumerate(installment_values):
            due = new_due_date + timedelta(days=30 * i)
            nb = BillingEntry.objects.create(
                plan=billing.plan,
                student=billing.student,
                installment_number=next_installment + i,
                description=f"Renegociacao — {billing.description} "
                f"(Parcela {i + 1}/{installment_count})",
                original_value=amount,
                discount_value=ZERO,
                paid_value=ZERO,
                due_date=due,
                status=BillingEntry.Status.OPEN,
                renegotiated_from=billing,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", nb)
            new_billings.append(nb)

        self._log(
            "Cobranca renegociada",
            billing_id=str(billing.pk),
            new_count=installment_count,
            new_value=str(renegotiated_value),
        )
        return new_billings

    def apply_late_fees(self, billing_id, *, reference_date: date | None = None) -> BillingEntry:
        """Aplica multa e juros de mora a uma cobranca vencida, recalculando o valor original.

        A multa e juros sao acrescentados ao `original_value`, preservando
        o `discount_value`. Idempotente: se ja aplicado (flag em `notes`), nao reaplica.
        """
        from financeiro.models import BillingEntry

        try:
            billing = BillingEntry.objects.get(pk=billing_id)
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None

        if billing.status != BillingEntry.Status.OVERDUE:
            raise BusinessRuleViolationError(
                "Apenas cobrancas vencidas podem ter multa e juros aplicados."
            )

        if "[multa-aplicada]" in billing.notes:
            return billing

        plan = billing.plan
        reference = reference_date or date.today()
        days_late = (reference - billing.due_date).days
        if days_late <= 0:
            raise BusinessRuleViolationError(
                "Cobranca nao esta em atraso em relacao a data informada."
            )

        late_fee = (billing.original_value * plan.late_fee_percent / Decimal("100")).quantize(
            Decimal("0.01")
        )
        interest = (
            billing.original_value
            * plan.daily_interest_percent
            * Decimal(days_late)
            / Decimal("100")
        ).quantize(Decimal("0.01"))

        old_values = {
            "original_value": str(billing.original_value),
            "notes": billing.notes,
            "version": billing.version,
        }
        billing.original_value = billing.original_value + late_fee + interest
        billing.notes = (
            (billing.notes or "")
            + f"\n[multa-aplicada] dias={days_late} multa={late_fee} \
juros={interest}"
        )
        billing.updated_by = self.user
        billing.save(
            update_fields=["original_value", "notes", "updated_by", "updated_at", "version"]
        )
        self._record_audit("UPDATE", billing, old_values=old_values)
        self._log(
            "Multa e juros aplicados",
            billing_id=str(billing.pk),
            days_late=days_late,
            late_fee=str(late_fee),
            interest=str(interest),
        )
        return billing

    def refresh_overdue_status(self, *, reference_date: date | None = None) -> int:
        """Varredura que marca cobrancas OPEN vencidas como OVERDUE. Operacao para scheduler.

        Returns:
            Quantidade de cobrancas atualizadas.
        """
        from financeiro.models import BillingEntry

        reference = reference_date or date.today()
        qs = BillingEntry.objects.filter(status=BillingEntry.Status.OPEN, due_date__lt=reference)
        count = 0
        for billing in qs:
            old_status = billing.status
            billing.status = BillingEntry.Status.OVERDUE
            billing.updated_by = self.user
            billing.save(update_fields=["status", "updated_by", "updated_at", "version"])
            self._record_audit("UPDATE", billing, old_values={"status": old_status})
            count += 1
        if count:
            self._log(
                "Status vencido atualizado em lote", updated_count=count, reference=str(reference)
            )
        return count
