"""Regras e cálculos compartilhados pelo financeiro."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from base.exceptions import ObjectNotFoundError, ValidationError

if TYPE_CHECKING:
    from financeiro.models import StudentFinancialContract

ZERO = Decimal("0.00")


class FinanceRulesMixin:
    """Invariantes e cálculos puros usados pelos serviços financeiros."""

    ACTIVE_CONTRACT_STATUSES = ("ACTIVE",)

    def _get_contract(self, contract_id) -> StudentFinancialContract:
        from financeiro.models import StudentFinancialContract

        try:
            return (
                StudentFinancialContract.objects.select_for_update(of=("self",))
                .select_related("student", "class_obj")
                .get(pk=contract_id)
            )
        except StudentFinancialContract.DoesNotExist:
            raise ObjectNotFoundError("StudentFinancialContract", str(contract_id)) from None

    @staticmethod
    def _to_decimal(value, default: Decimal = ZERO) -> Decimal:
        if value in (None, ""):
            return default
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except (ArithmeticError, ValueError):
            raise ValidationError(errors={"value": ["Valor monetario invalido."]}) from None

    @staticmethod
    def _month_step(frequency: str) -> int:
        return {
            "MONTHLY": 1,
            "BIMONTHLY": 2,
            "QUARTERLY": 3,
            "ANNUAL": 12,
        }.get(frequency, 1)

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        """Avança competências pelo calendário preservando o primeiro dia do mês."""
        absolute = value.year * 12 + value.month - 1 + months
        return date(absolute // 12, absolute % 12 + 1, 1)

    @staticmethod
    def _next_installment_number(contract_id) -> int:
        from django.db.models import Max

        from financeiro.models import BillingEntry

        current = (
            BillingEntry.all_objects.filter(contract_id=contract_id).aggregate(
                max_number=Max("installment_number")
            )["max_number"]
            or 0
        )
        return current + 1

    @staticmethod
    def _split_amount(amount: Decimal, installment_count: int) -> list[Decimal]:
        """Divide um valor em parcelas sem perder centavos."""
        total_cents = int((amount * Decimal("100")).to_integral_value())
        base_cents, remainder = divmod(total_cents, installment_count)
        values = [Decimal(base_cents) / Decimal("100") for _ in range(installment_count)]
        values[-1] += Decimal(remainder) / Decimal("100")
        return values

    def _validated_payment_terms(self, data: dict) -> dict:
        """Normaliza e valida os termos financeiros compartilhados."""
        from financeiro.models import StudentFinancialContract

        try:
            count = int(data["installment_count"])
        except (TypeError, ValueError):
            raise ValidationError(
                errors={"installment_count": ["Informe entre 1 e 60 parcelas."]}
            ) from None
        value = self._to_decimal(data["installment_value"])
        discount = self._to_decimal(data.get("discount_value", 0))
        late_fee = self._to_decimal(data.get("late_fee_percent", 0))
        try:
            interest = Decimal(str(data.get("daily_interest_percent", 0))).quantize(
                Decimal("0.0001")
            )
        except (ArithmeticError, ValueError):
            raise ValidationError(
                errors={"daily_interest_percent": ["Encargo inválido."]}
            ) from None
        try:
            due_day = int(data["due_day"])
        except (TypeError, ValueError):
            raise ValidationError(errors={"due_day": ["Informe um dia entre 1 e 28."]}) from None
        if count < 1 or count > 60:
            raise ValidationError(errors={"installment_count": ["Informe entre 1 e 60 parcelas."]})
        if value <= ZERO:
            raise ValidationError(errors={"installment_value": ["O valor deve ser positivo."]})
        if discount < ZERO or discount >= value:
            raise ValidationError(
                errors={"discount_value": ["O desconto deve ser menor que o valor da parcela."]}
            )
        if due_day < 1 or due_day > 28:
            raise ValidationError(errors={"due_day": ["Informe um dia entre 1 e 28."]})
        if late_fee < ZERO or interest < ZERO:
            raise ValidationError(
                errors={"late_fee_percent": ["Encargos não podem ser negativos."]}
            )
        frequency = data.get("billing_frequency", StudentFinancialContract.BillingFrequency.MONTHLY)
        if frequency not in StudentFinancialContract.BillingFrequency.values:
            raise ValidationError(errors={"billing_frequency": ["Frequência inválida."]})
        return {
            "billing_frequency": frequency,
            "installment_count": count,
            "installment_value": value,
            "due_day": due_day,
            "discount_value": discount,
            "late_fee_percent": late_fee,
            "daily_interest_percent": interest,
        }

    def _validated_contract_values(self, data: dict) -> dict:
        """Valida os termos e adiciona a identificação do contrato."""
        return {
            "academic_year": int(data["academic_year"]),
            "name": str(data["name"]).strip(),
            **self._validated_payment_terms(data),
        }

    def _validated_template_values(self, data: dict) -> dict:
        """Valida os termos e adiciona os metadados do modelo reutilizável."""
        return {
            **self._validated_contract_values(data),
            "description": str(data.get("description", "")).strip(),
        }
