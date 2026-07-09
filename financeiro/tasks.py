"""Tarefas Celery do modulo Financeiro Escolar."""

from __future__ import annotations

import logging

from celery import shared_task

from base.context import tenant_schema_context

logger = logging.getLogger(__name__)


@shared_task(name="financeiro.refresh_overdue")
def refresh_overdue_task(tenant_schema: str) -> int:
    """Varredura periodica que marca cobrancas OPEN vencidas como OVERDUE."""
    with tenant_schema_context(tenant_schema):
        from financeiro.services import FinanceService

        # User None: operacao de sistema, sem executor humano.
        count = FinanceService(user=None).refresh_overdue_status()
        logger.info("refresh_overdone concluido", extra={"updated": count})
        return count


@shared_task(name="financeiro.charge_via_gateway")
def charge_via_gateway_task(tenant_schema: str, billing_id: str) -> str:
    """Envia a cobranca para o gateway configurado (adaptador), sem acoplamento direto."""
    with tenant_schema_context(tenant_schema):
        from financeiro.gateway import get_payment_gateway
        from financeiro.selectors import BillingSelector

        billing = BillingSelector().get_billing_by_id(billing_id)
        result = get_payment_gateway().create_charge(
            billing_id=billing.pk,
            amount=billing.outstanding_value,
            due_date=billing.due_date,
            description=billing.description,
        )
        if not result.success:
            logger.warning(
                "Falha ao criar cobranca no gateway",
                extra={"billing_id": str(billing.pk), "erro": result.error_message},
            )
        return result.external_id
