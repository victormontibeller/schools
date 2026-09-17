"""Enfileiramento idempotente de lembretes documentais."""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from base.context import active_tenant_schema, require_tenant_schema
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
from base.services import BaseService, system_command
from enrollments.services.validation import ApplicationValidationMixin

logger = logging.getLogger(__name__)


class EnrollmentReminderService(BaseService):
    """Cria lembretes e publica tarefas somente depois do commit."""

    CLAIM_TIMEOUT = timedelta(minutes=15)

    def send_reminders(self, application_id, *, expected_version: int):
        """Enfileira e-mail genérico para os destinatários consentidos elegíveis."""
        from enrollments.models import EnrollmentReminder, StudentDocument
        from enrollments.selectors import EnrollmentApplicationSelector
        from enrollments.services.applications import EnrollmentApplicationService

        selector = EnrollmentApplicationSelector()
        application = EnrollmentApplicationService._lock_application(
            application_id, expected_version
        )
        if (
            not StudentDocument.objects.filter(application=application, is_required=True)
            .exclude(status__in=[StudentDocument.Status.VERIFIED, StudentDocument.Status.WAIVED])
            .exists()
        ):
            raise BusinessRuleViolationError("A solicitação não possui documentos pendentes.")
        recipient_ids = selector.reminder_recipient_ids(application_id)
        if not recipient_ids:
            raise BusinessRuleViolationError("Não há destinatário consentido para este lembrete.")
        schema = active_tenant_schema()
        reminders = []
        for recipient_id in recipient_ids:
            reminder, created = EnrollmentReminder.objects.get_or_create(
                application=application,
                recipient_id=recipient_id,
                defaults={"created_by": self.user, "updated_by": self.user},
            )
            if created:
                self._record_audit("INSERT", reminder, new_values=self._snapshot(reminder))
            if created:
                reminders.append(reminder)
            elif reminder.status == EnrollmentReminder.Status.FAILED:
                old = self._snapshot(reminder)
                reminder.status = EnrollmentReminder.Status.PENDING
                reminder.message_log_id = None
                reminder.sent_at = None
                reminder.updated_by = self.user
                reminder.save(
                    update_fields=[
                        "status",
                        "message_log_id",
                        "sent_at",
                        "updated_by",
                        "updated_at",
                    ]
                )
                self._record_audit(
                    "UPDATE",
                    reminder,
                    old_values=old,
                    new_values=self._snapshot(reminder),
                )
                reminders.append(reminder)
        if reminders:
            from enrollments.tasks import send_enrollment_document_reminder

            for reminder in reminders:
                transaction.on_commit(
                    lambda reminder_id=str(reminder.pk): self._publish_reminder(
                        send_enrollment_document_reminder, schema, reminder_id
                    )
                )
        self._log(
            "enrollment_reminders_enqueued",
            application_id=str(application.pk),
            reminder_count=len(reminders),
        )
        return reminders

    @staticmethod
    def _publish_reminder(
        task,
        schema: str,
        reminder_id: str,
        *,
        message_log_id: str | None = None,
    ) -> None:
        try:
            kwargs = {"tenant_schema": schema, "reminder_id": reminder_id}
            if message_log_id:
                kwargs["message_log_id"] = message_log_id
            task.delay(**kwargs)
        except Exception as exc:
            logger.error(
                "enrollment_reminder_publish_failed",
                extra={
                    "reminder_id": reminder_id,
                    "error_type": type(exc).__name__,
                },
            )
            with transaction.atomic():
                if message_log_id:
                    from notifications.channels import ChannelResult
                    from notifications.delivery_services import MessageDeliveryService

                    MessageDeliveryService(user=None).record_channel_result(
                        message_log_id,
                        ChannelResult(
                            success=False,
                            channel="EMAIL",
                            recipient_address="",
                            error_message="task_publish_failed",
                        ),
                    )
                EnrollmentReminderService(user=None).record_delivery_result(
                    reminder_id,
                    tenant_schema=schema,
                    success=False,
                    message_log_id=message_log_id,
                )

    @system_command
    def claim_for_delivery(self, reminder_id, *, tenant_schema: str, message_log_id=None):
        """Faz claim exclusivo antes da chamada externa ou retoma um retry conhecido."""
        require_tenant_schema(tenant_schema)
        from enrollments.models import EnrollmentReminder

        normalized_reminder_id = ApplicationValidationMixin._normalize_uuid(
            reminder_id, "reminder_id"
        )
        normalized_message_log_id = ApplicationValidationMixin._normalize_optional_uuid(
            message_log_id, "message_log_id"
        )
        try:
            reminder = (
                EnrollmentReminder.objects.select_for_update()
                .select_related("recipient", "application")
                .get(pk=normalized_reminder_id)
            )
        except EnrollmentReminder.DoesNotExist:
            raise ObjectNotFoundError("EnrollmentReminder", str(reminder_id)) from None
        if reminder.status in {
            EnrollmentReminder.Status.SENT,
            EnrollmentReminder.Status.FAILED,
        }:
            return None
        from enrollments.selectors import EnrollmentApplicationSelector

        if not EnrollmentApplicationSelector().is_reminder_recipient_eligible(
            reminder.application_id, reminder.recipient_id
        ):
            old = self._snapshot(reminder)
            reminder.status = EnrollmentReminder.Status.FAILED
            reminder.sent_at = None
            reminder.updated_by = self.user
            reminder.save(update_fields=["status", "sent_at", "updated_by", "updated_at"])
            self._record_audit(
                "UPDATE",
                reminder,
                old_values=old,
                new_values=self._snapshot(reminder),
            )
            self._log(
                "enrollment_reminder_recipient_ineligible",
                reminder_id=str(reminder.pk),
            )
            return None
        if reminder.status == EnrollmentReminder.Status.SENDING:
            if normalized_message_log_id and reminder.message_log_id == normalized_message_log_id:
                return reminder if self._reconcile_stale_message_log(reminder) else None
            if (
                not message_log_id
                and reminder.message_log_id
                and reminder.updated_at <= timezone.now() - self.CLAIM_TIMEOUT
            ):
                return reminder if self._reconcile_stale_message_log(reminder) else None
            return None
        if reminder.status != EnrollmentReminder.Status.PENDING or normalized_message_log_id:
            return None
        old = self._snapshot(reminder)
        if reminder.message_log_id is None:
            from notifications.delivery_services import MessageDeliveryService

            message_log = MessageDeliveryService(user=None).create_pending(
                recipient=reminder.recipient,
                channel="EMAIL",
                recipient_address=reminder.recipient.email,
            )
            reminder.message_log_id = message_log.pk
        reminder.status = EnrollmentReminder.Status.SENDING
        reminder.save(update_fields=["status", "message_log_id", "updated_at"])
        self._record_audit(
            "UPDATE",
            reminder,
            old_values=old,
            new_values=self._snapshot(reminder),
        )
        self._log(
            "enrollment_reminder_claimed",
            reminder_id=str(reminder.pk),
            message_log_id=str(reminder.message_log_id),
            from_status=EnrollmentReminder.Status.PENDING,
            to_status=EnrollmentReminder.Status.SENDING,
        )
        return reminder

    @system_command
    def reconcile_stale_claims(self, *, tenant_schema: str) -> int:
        """Retoma claims expirados e sincroniza logs já encerrados pelo transporte."""
        schema = require_tenant_schema(tenant_schema)
        from enrollments.models import EnrollmentReminder
        from enrollments.tasks import send_enrollment_document_reminder

        cutoff = timezone.now() - self.CLAIM_TIMEOUT
        stale_reminders = list(
            EnrollmentReminder.objects.select_for_update()
            .filter(
                status__in=[
                    EnrollmentReminder.Status.PENDING,
                    EnrollmentReminder.Status.SENDING,
                ],
                updated_at__lte=cutoff,
            )
            .order_by("pk")
        )
        recovered = 0
        for reminder in stale_reminders:
            if reminder.status == EnrollmentReminder.Status.PENDING:
                if reminder.message_log_id:
                    if not self._reconcile_stale_message_log(reminder):
                        continue
                else:
                    old = self._snapshot(reminder)
                    reminder.updated_by = self.user
                    reminder.save(update_fields=["updated_by", "updated_at"])
                    self._record_audit(
                        "UPDATE",
                        reminder,
                        old_values=old,
                        new_values=self._snapshot(reminder),
                    )
                    self._log(
                        "enrollment_reminder_pending_recovered",
                        reminder_id=str(reminder.pk),
                    )
                recovered += 1
                transaction.on_commit(
                    lambda reminder_id=str(reminder.pk): self._publish_reminder(
                        send_enrollment_document_reminder,
                        schema,
                        reminder_id,
                    )
                )
                continue
            if not self._reconcile_stale_message_log(reminder):
                continue
            recovered += 1
            transaction.on_commit(
                lambda reminder_id=str(reminder.pk), message_log_id=str(
                    reminder.message_log_id
                ): self._publish_reminder(
                    send_enrollment_document_reminder,
                    schema,
                    reminder_id,
                    message_log_id=message_log_id,
                )
            )
        self._log(
            "enrollment_stale_reminders_reconciled",
            stale_count=len(stale_reminders),
            recovered_count=recovered,
        )
        return recovered

    def _reconcile_stale_message_log(self, reminder) -> bool:
        """Retorna ``True`` somente quando o mesmo log pendente deve ser republicado."""
        from enrollments.models import EnrollmentReminder
        from notifications.contracts import MessageLog

        message_log = (
            MessageLog.all_objects.filter(pk=reminder.message_log_id).first()
            if reminder.message_log_id
            else None
        )
        old = self._snapshot(reminder)
        if message_log and message_log.status == MessageLog.Status.PENDING:
            reminder.updated_at = timezone.now()
            reminder.updated_by = self.user
            reminder.save(update_fields=["updated_at", "updated_by"])
            self._record_audit(
                "UPDATE",
                reminder,
                old_values=old,
                new_values=self._snapshot(reminder),
            )
            self._log(
                "enrollment_reminder_claim_resumed",
                reminder_id=str(reminder.pk),
            )
            return True

        successful_statuses = {
            MessageLog.Status.SENT,
            MessageLog.Status.DELIVERED,
            MessageLog.Status.DELAYED,
        }
        reminder.status = (
            EnrollmentReminder.Status.SENT
            if message_log and message_log.status in successful_statuses
            else EnrollmentReminder.Status.FAILED
        )
        reminder.sent_at = (
            message_log.sent_at or message_log.delivered_at or timezone.now()
            if reminder.status == EnrollmentReminder.Status.SENT
            else None
        )
        reminder.updated_by = self.user
        reminder.save(update_fields=["status", "sent_at", "updated_by", "updated_at"])
        self._record_audit(
            "UPDATE",
            reminder,
            old_values=old,
            new_values=self._snapshot(reminder),
        )
        self._log(
            "enrollment_reminder_abandoned_claim_closed",
            reminder_id=str(reminder.pk),
            success=reminder.status == EnrollmentReminder.Status.SENT,
        )
        return False

    @system_command
    def record_delivery_result(
        self,
        reminder_id,
        *,
        tenant_schema: str,
        success: bool,
        message_log_id=None,
    ):
        """Persiste o resultado sanitizado produzido pelo transporte canônico."""
        require_tenant_schema(tenant_schema)
        from enrollments.models import EnrollmentReminder

        normalized_reminder_id = ApplicationValidationMixin._normalize_uuid(
            reminder_id, "reminder_id"
        )
        normalized_message_log_id = ApplicationValidationMixin._normalize_optional_uuid(
            message_log_id, "message_log_id"
        )
        try:
            reminder = EnrollmentReminder.objects.select_for_update().get(pk=normalized_reminder_id)
        except EnrollmentReminder.DoesNotExist:
            raise ObjectNotFoundError("EnrollmentReminder", str(reminder_id)) from None
        if reminder.status == EnrollmentReminder.Status.SENT:
            return reminder
        if reminder.status not in {
            EnrollmentReminder.Status.PENDING,
            EnrollmentReminder.Status.SENDING,
        }:
            return reminder
        if (
            normalized_message_log_id
            and reminder.message_log_id
            and normalized_message_log_id != reminder.message_log_id
        ):
            return reminder
        old = self._snapshot(reminder)
        reminder.status = (
            EnrollmentReminder.Status.SENT if success else EnrollmentReminder.Status.FAILED
        )
        reminder.message_log_id = normalized_message_log_id or reminder.message_log_id
        reminder.sent_at = timezone.now() if success else None
        reminder.updated_by = self.user
        reminder.save(
            update_fields=["status", "message_log_id", "sent_at", "updated_by", "updated_at"]
        )
        self._record_audit(
            "UPDATE",
            reminder,
            old_values=old,
            new_values=self._snapshot(reminder),
        )
        self._log(
            "enrollment_reminder_result_recorded",
            reminder_id=str(reminder.pk),
            success=success,
        )
        return reminder
