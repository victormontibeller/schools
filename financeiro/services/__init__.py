"""Serviços públicos do domínio financeiro."""

from base.services import BaseService
from financeiro.services.billings import BillingLifecycleMixin
from financeiro.services.payments import PaymentService
from financeiro.services.plans import PlanLifecycleMixin
from financeiro.services.rules import FinanceRulesMixin


class FinanceService(
    PlanLifecycleMixin,
    BillingLifecycleMixin,
    FinanceRulesMixin,
    BaseService,
):
    """Coordena planos financeiros e cobranças."""


__all__ = ["FinanceService", "PaymentService"]
