"""Serviços públicos do domínio financeiro."""

from base.services import BaseService
from financeiro.services.amendments import ContractAmendmentMixin
from financeiro.services.billings import BillingLifecycleMixin
from financeiro.services.contracts import ContractLifecycleMixin
from financeiro.services.payments import PaymentService
from financeiro.services.reminders import ReminderLifecycleMixin
from financeiro.services.rules import FinanceRulesMixin
from financeiro.services.templates import TemplateLifecycleMixin


class FinanceService(
    TemplateLifecycleMixin,
    ContractAmendmentMixin,
    ContractLifecycleMixin,
    BillingLifecycleMixin,
    ReminderLifecycleMixin,
    FinanceRulesMixin,
    BaseService,
):
    """Coordena planos financeiros e cobranças."""


__all__ = ["FinanceService", "PaymentService"]
