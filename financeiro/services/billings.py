"""Comandos seguros sobre cobranças financeiras."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import service_command
from financeiro.services.rules import ZERO


class BillingLifecycleMixin:
    """Lançamento, cancelamento, encargos e renegociação de cobranças."""

    @service_command
    def create_ad_hoc_billing(self, data: dict):
        """Cria uma cobrança avulsa sem exigir contrato financeiro."""
        from financeiro.models import BillingEntry
        from students.contracts import Student

        self.validate_required(data, ["student_id", "description", "amount", "due_date"])
        try:
            student = Student.objects.get(pk=data["student_id"])
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(data["student_id"])) from None
        amount = self._to_decimal(data["amount"])
        discount = self._to_decimal(data.get("discount_value", 0))
        if amount <= ZERO or discount < ZERO or discount >= amount:
            raise ValidationError(errors={"amount": ["Informe um valor líquido positivo."]})
        due_date = data["due_date"]
        if not isinstance(due_date, date):
            raise ValidationError(errors={"due_date": ["Data de vencimento inválida."]})
        billing = BillingEntry.objects.create(
            contract=None,
            student=student,
            installment_number=None,
            category=data.get("category", BillingEntry.Category.FEE),
            description=str(data["description"]).strip(),
            principal_value=amount,
            discount_value=discount,
            competency=(data.get("competency") or due_date).replace(day=1),
            due_date=due_date,
            notes=str(data.get("notes", "")).strip(),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", billing)
        self._log(
            "ad_hoc_billing_created",
            billing_id=str(billing.pk),
            student_id=str(student.pk),
            category=billing.category,
        )
        return billing

    @service_command
    def cancel_billing(self, billing_id, reason: str = ""):
        """Cancela cobrança sem pagamento confirmado, preservando o histórico."""
        from financeiro.models import BillingEntry

        try:
            billing = BillingEntry.objects.select_for_update().get(pk=billing_id)
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None
        if billing.status == BillingEntry.Status.CANCELLED:
            raise BusinessRuleViolationError("Cobrança já está cancelada.")
        if billing.paid_value > ZERO:
            raise BusinessRuleViolationError("Cobrança com pagamento não pode ser cancelada.")
        if not reason.strip():
            raise ValidationError(errors={"reason": ["Informe o motivo do cancelamento."]})
        old = {"status": billing.status, "cancelled_reason": billing.cancelled_reason}
        billing.status = BillingEntry.Status.CANCELLED
        billing.cancelled_reason = reason.strip()
        billing.updated_by = self.user
        billing.save()
        self._record_audit("DELETE", billing, old_values=old)
        self._log("billing_cancelled", billing_id=str(billing.pk))
        return billing

    @service_command
    def renegotiate_billing(
        self,
        billing_id,
        *,
        new_due_date: date,
        new_value: Decimal | None = None,
        installment_count: int = 1,
    ) -> list:
        """Substitui o saldo de uma cobrança por novas parcelas mensais."""
        from financeiro.models import BillingEntry

        try:
            billing = (
                BillingEntry.objects.select_for_update(of=("self",))
                .select_related("contract")
                .get(pk=billing_id)
            )
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None
        if billing.status == BillingEntry.Status.CANCELLED or billing.is_settled:
            raise BusinessRuleViolationError("Cobrança encerrada não pode ser renegociada.")
        if not isinstance(new_due_date, date):
            raise ValidationError(errors={"new_due_date": ["Data de vencimento inválida."]})
        if installment_count < 1 or installment_count > 12:
            raise ValidationError(errors={"installment_count": ["Informe entre 1 e 12 parcelas."]})
        self._assess_late_charges(billing, new_due_date)
        amount = self._to_decimal(new_value) if new_value is not None else billing.outstanding_value
        if amount <= ZERO:
            raise ValidationError(errors={"new_value": ["O valor deve ser positivo."]})
        values = self._split_amount(amount, installment_count)
        old_status = billing.status
        billing.status = BillingEntry.Status.CANCELLED
        billing.cancelled_reason = "Renegociação"
        billing.updated_by = self.user
        billing.save()
        self._record_audit("DELETE", billing, old_values={"status": old_status})

        number = self._next_installment_number(billing.contract_id) if billing.contract_id else None
        result = []
        for index, value in enumerate(values):
            competency = self._add_months(new_due_date.replace(day=1), index)
            replacement = BillingEntry.objects.create(
                contract=billing.contract,
                student=billing.student,
                installment_number=number + index,
                schedule_revision=(billing.contract.terms_revision if billing.contract else 1),
                category=BillingEntry.Category.ADJUSTMENT,
                description=(
                    f"Renegociação - {billing.description} " f"({index + 1}/{installment_count})"
                ),
                principal_value=value,
                competency=competency,
                due_date=competency.replace(day=min(new_due_date.day, 28)),
                renegotiated_from=billing,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", replacement)
            result.append(replacement)
        self._log(
            "billing_renegotiated",
            billing_id=str(billing.pk),
            replacement_count=len(result),
        )
        return result

    @service_command
    def assess_late_charges(self, billing_id, *, reference_date: date | None = None):
        """Apura multa única e juros incrementais sem modificar o principal."""
        from financeiro.models import BillingEntry

        try:
            billing = (
                BillingEntry.objects.select_for_update(of=("self",))
                .select_related("contract")
                .get(pk=billing_id)
            )
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None
        self._assess_late_charges(billing, reference_date or date.today())
        return billing

    def _assess_late_charges(self, billing, reference: date) -> None:
        if billing.status == billing.Status.CANCELLED or billing.is_settled:
            return
        if reference <= billing.due_date or not billing.contract_id:
            return
        contract = billing.contract
        old = {
            "late_fee_value": str(billing.late_fee_value),
            "interest_value": str(billing.interest_value),
            "interest_calculated_until": billing.interest_calculated_until,
        }
        if billing.late_fee_value == ZERO:
            billing.late_fee_value = (
                billing.contractual_value * contract.late_fee_percent / Decimal("100")
            ).quantize(Decimal("0.01"))
        start = billing.interest_calculated_until or billing.due_date
        if reference < start:
            raise BusinessRuleViolationError(
                "Não é possível apurar pagamento anterior à última apuração de juros."
            )
        days = (reference - start).days
        outstanding_principal = max(
            billing.contractual_value - billing.paid_principal_value,
            ZERO,
        )
        if days > 0 and outstanding_principal > ZERO:
            billing.interest_value += (
                outstanding_principal
                * contract.daily_interest_percent
                * Decimal(days)
                / Decimal("100")
            ).quantize(Decimal("0.01"))
            billing.interest_calculated_until = reference
        billing.updated_by = self.user
        billing.save()
        if old != {
            "late_fee_value": str(billing.late_fee_value),
            "interest_value": str(billing.interest_value),
            "interest_calculated_until": billing.interest_calculated_until,
        }:
            self._record_audit("UPDATE", billing, old_values=old)
            self._log(
                "billing_late_charges_assessed",
                billing_id=str(billing.pk),
                reference_date=reference.isoformat(),
            )

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        absolute = value.year * 12 + value.month - 1 + months
        return date(absolute // 12, absolute % 12 + 1, 1)
