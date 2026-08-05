"""Tasks tenant-scoped de lembretes do workflow de matrículas."""

from types import SimpleNamespace

from celery import shared_task

from base.context import tenant_schema_context


@shared_task(bind=True, max_retries=3, name="enrollments.send_enrollment_document_reminder")
def send_enrollment_document_reminder(
    self,
    tenant_schema: str,
    reminder_id: str,
    message_log_id: str | None = None,
) -> None:
    """Envia conteúdo externo genérico por ``MessageTransport`` e registra o resultado."""
    if not tenant_schema or tenant_schema == "public":
        return
    with tenant_schema_context(tenant_schema):
        from enrollments.services import EnrollmentReminderService
        from notifications.task_helpers import get_transport, retry_email_if_needed

        service = EnrollmentReminderService(user=None)
        reminder = service.claim_for_delivery(
            reminder_id,
            tenant_schema=tenant_schema,
            message_log_id=message_log_id,
        )
        if reminder is None:
            return
        try:
            transport = get_transport("EMAIL")
            result = transport.send_individual(
                reminder.recipient,
                SimpleNamespace(
                    subject="Pendência na Secretaria Escolar",
                    body=(
                        "Há uma pendência em um processo da Secretaria. "
                        "Acesse o School Manager ou procure a escola para orientações."
                    ),
                ),
                message_log_id=reminder.message_log_id,
                category="enrollment_document_reminder",
            )
        except Exception:
            if self.request.retries < self.max_retries:
                retry_kwargs = {
                    "tenant_schema": tenant_schema,
                    "reminder_id": reminder_id,
                    "message_log_id": str(reminder.message_log_id),
                }
                raise self.retry(
                    kwargs=retry_kwargs,
                    exc=RuntimeError("enrollment_reminder_transport_failed"),
                ) from None
            _record_unexpected_failure(reminder.message_log_id)
            service.record_delivery_result(
                reminder.pk,
                tenant_schema=tenant_schema,
                success=False,
                message_log_id=reminder.message_log_id,
            )
            return
        delivery_log_id = transport.last_log_id or reminder.message_log_id
        if not result and transport.last_result is None and delivery_log_id:
            from notifications.channels import ChannelResult
            from notifications.delivery_services import MessageDeliveryService

            MessageDeliveryService(user=None).record_channel_result(
                delivery_log_id,
                ChannelResult(
                    success=False,
                    channel="EMAIL",
                    recipient_address="",
                    error_message="recipient_not_eligible",
                ),
            )
        retry_email_if_needed(self, transport, result)
        service.record_delivery_result(
            reminder.pk,
            tenant_schema=tenant_schema,
            success=bool(result),
            message_log_id=delivery_log_id,
        )


@shared_task(name="enrollments.reconcile_stale_document_reminders")
def reconcile_stale_document_reminders(tenant_schema: str) -> int:
    """Reconcilia claims expirados dentro de um único schema escolar."""
    if not tenant_schema or tenant_schema == "public":
        return 0
    with tenant_schema_context(tenant_schema):
        from enrollments.services import EnrollmentReminderService

        return EnrollmentReminderService(user=None).reconcile_stale_claims(
            tenant_schema=tenant_schema
        )


@shared_task(name="enrollments.dispatch_stale_document_reminder_recovery")
def dispatch_stale_document_reminder_recovery() -> int:
    """Publica uma reconciliação isolada para cada escola ativa."""
    from tenancy.contracts import School

    tenant_schemas = list(
        School.objects.filter(is_active=True)
        .exclude(schema_name="public")
        .values_list("schema_name", flat=True)
    )
    for tenant_schema in tenant_schemas:
        reconcile_stale_document_reminders.delay(tenant_schema)
    return len(tenant_schemas)


def _record_unexpected_failure(message_log_id) -> None:
    """Fecha o log conhecido com código genérico, sem persistir conteúdo da exceção."""
    if not message_log_id:
        return
    from notifications.channels import ChannelResult
    from notifications.delivery_services import MessageDeliveryService

    MessageDeliveryService(user=None).record_channel_result(
        message_log_id,
        ChannelResult(
            success=False,
            channel="EMAIL",
            recipient_address="",
            error_message="unexpected_delivery_failure",
        ),
    )
