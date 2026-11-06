"""Tarefas Celery do modulo Financeiro Escolar."""

from __future__ import annotations

import logging
from datetime import date

from celery import shared_task
from django.utils import timezone

from base.context import tenant_schema_context
from base.events import publish_task_safely

logger = logging.getLogger(__name__)


@shared_task(name="financeiro.process_collection_reminders")
def process_collection_reminders_task(tenant_schema: str, reference_date: str | None = None) -> int:
    """Executa a régua habilitada no schema explícito da escola."""
    with tenant_schema_context(tenant_schema):
        from financeiro.services import FinanceService

        parsed = date.fromisoformat(reference_date) if reference_date else timezone.localdate()
        return FinanceService(user=None).run_scheduled_reminders(reference_date=parsed)


@shared_task(name="financeiro.dispatch_collection_reminders")
def dispatch_collection_reminders_task() -> int:
    """Publica uma execução tenant-scoped para cada escola ativa."""
    from tenancy.selectors import SchoolSelector

    published = 0
    for schema_name in SchoolSelector().list_active_schemas().iterator():
        if publish_task_safely(
            process_collection_reminders_task,
            schema_name,
            tenant_schema=schema_name,
        ):
            published += 1
    return published


@shared_task(name="financeiro.charge_via_gateway")
def charge_via_gateway_task(tenant_schema: str, billing_id: str) -> str:
    """Envia a cobranca para o gateway configurado (adaptador), sem acoplamento direto."""
    with tenant_schema_context(tenant_schema):
        from financeiro.gateway import get_payment_gateway
        from financeiro.selectors import BillingSelector
        from tenancy.selectors import SchoolSelector

        SchoolSelector().get_active_by_schema(tenant_schema)
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
                extra={"billing_id": str(billing.pk), "gateway_status": "failed"},
            )
        return result.external_id
