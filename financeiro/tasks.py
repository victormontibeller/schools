"""Tarefas Celery do modulo Financeiro Escolar."""

from __future__ import annotations

import logging
from datetime import date
from types import SimpleNamespace

from celery import shared_task

from base.context import tenant_schema_context

logger = logging.getLogger(__name__)


@shared_task(name="financeiro.process_collection_reminders")
def process_collection_reminders_task(tenant_schema: str, reference_date: str | None = None) -> int:
    """Executa a régua habilitada no schema explícito da escola."""
    with tenant_schema_context(tenant_schema):
        from financeiro.services import FinanceService

        parsed = date.fromisoformat(reference_date) if reference_date else date.today()
        return FinanceService(user=None).run_scheduled_reminders(reference_date=parsed)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def deliver_collection_reminder_task(self, tenant_schema: str, reminder_id: str) -> None:
    """Entrega mensagem genérica e revalida acesso, guarda e saldo."""
    with tenant_schema_context(tenant_schema):
        from core.permissions import can_access
        from financeiro.models import CollectionReminder
        from financeiro.services import FinanceService
        from guardians.contracts import StudentGuardian

        reminder = (
            CollectionReminder.objects.select_related("billing", "guardian", "recipient")
            .filter(pk=reminder_id, status=CollectionReminder.Status.PENDING)
            .first()
        )
        if reminder is None:
            return
        service = FinanceService(user=None)
        valid_guard = StudentGuardian.objects.filter(
            student_id=reminder.billing.student_id,
            guardian_id=reminder.guardian_id,
            has_custody=True,
            guardian__is_active=True,
        ).exists()
        if (
            not valid_guard
            or reminder.recipient is None
            or not reminder.recipient.is_active
            or not can_access(reminder.recipient, "finance_billings", "view")
            or reminder.billing.status == reminder.billing.Status.CANCELLED
            or reminder.billing.outstanding_value <= 0
        ):
            service.complete_reminder_delivery(
                reminder.pk,
                status=CollectionReminder.Status.SKIPPED,
                error_code="eligibility_changed",
            )
            return
        action_url = f"/financeiro/cobrancas/{reminder.billing_id}/"
        if reminder.channel == "IN_APP":
            from notifications.services import NotificationService

            NotificationService(user=None).create_notification(
                {
                    "recipient_id": reminder.recipient_id,
                    "title": "Atualização financeira disponível",
                    "message": "Há uma atualização financeira disponível no portal.",
                    "source": "financeiro",
                    "action_url": action_url,
                }
            )
            service.complete_reminder_delivery(reminder.pk, status=CollectionReminder.Status.SENT)
            return
        if reminder.channel != "EMAIL" or not reminder.guardian.accepts_email_notifications:
            service.complete_reminder_delivery(
                reminder.pk,
                status=CollectionReminder.Status.SKIPPED,
                error_code="channel_not_allowed",
            )
            return
        from notifications.task_helpers import get_transport, retry_email_if_needed

        transport = get_transport("EMAIL")
        result = transport.send_individual(
            reminder.recipient,
            SimpleNamespace(
                subject="Atualização financeira disponível",
                body="Há uma atualização financeira disponível no portal: {{ action_url }}",
            ),
            {"action_url": action_url},
            message_log_id=reminder.message_log_id,
            category="financial_reminder",
        )
        if result:
            service.complete_reminder_delivery(
                reminder.pk,
                status=CollectionReminder.Status.SENT,
                message_log_id=transport.last_log_id,
            )
            return
        if transport.last_result and transport.last_result.retryable:
            if reminder.message_log_id is None and transport.last_log_id:
                service.attach_reminder_message_log(reminder.pk, transport.last_log_id)
            retry_email_if_needed(self, transport, result)
            return
        service.complete_reminder_delivery(
            reminder.pk,
            status=CollectionReminder.Status.FAILED,
            message_log_id=transport.last_log_id,
            error_code="delivery_failed",
        )


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
                extra={"billing_id": str(billing.pk), "gateway_status": "failed"},
            )
        return result.external_id
