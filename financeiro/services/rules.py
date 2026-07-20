"""Regras e cálculos compartilhados pelo financeiro."""

from __future__ import annotations

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
            return StudentFinancialContract.objects.select_related("student", "class_obj").get(
                pk=contract_id
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
    def _normalize_month(year: int, month: int) -> tuple[int, int]:
        """Normaliza month > 12 rolando para o ano seguinte."""
        while month > 12:
            month -= 12
            year += 1
        return year, month

    @staticmethod
    def _installment_for_month(contract, month: int) -> int | None:
        """Calcula o numero da parcela esperada para o mes (1-based) ou None."""
        step = FinanceRulesMixin._month_step(contract.billing_frequency)
        if step == 0:
            return None
        index = (month - 1) // step + 1
        if index > contract.installment_count:
            return None
        return index

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
