"""Lembretes documentais com intenção durável compartilhada e sem pipeline paralelo."""

from django.urls import reverse

from base.context import active_tenant_schema
from base.exceptions import BusinessRuleViolationError
from base.services import BaseService


class EnrollmentReminderService(BaseService):
    def send_reminders(self, application_id, *, expected_version):
        from core.contracts import CustomUser
        from enrollments.models import EnrollmentReminder, StudentDocument
        from enrollments.selectors import EnrollmentApplicationSelector
        from enrollments.services.applications import EnrollmentApplicationService
        from notifications.outbox_services import OutboxService
        from notifications.projection_services import DeliveryProjectionService
        from tenancy.selectors import SchoolSelector

        SchoolSelector().get_active_by_schema(active_tenant_schema())
        application = EnrollmentApplicationService._lock_application(
            application_id, expected_version
        )
        if (
            not StudentDocument.objects.filter(application=application, is_required=True)
            .exclude(status__in=["VERIFIED", "WAIVED"])
            .exists()
        ):
            raise BusinessRuleViolationError("A solicitação não possui documentos pendentes.")
        ids = EnrollmentApplicationSelector().reminder_recipient_ids(application_id)
        if not ids:
            raise BusinessRuleViolationError(
                "Não há responsável principal elegível para este lembrete."
            )
        results = []
        for user in CustomUser.objects.filter(pk__in=ids):
            reminder, created = EnrollmentReminder.objects.get_or_create(
                application=application,
                recipient=user,
                defaults={"created_by": self.user, "updated_by": self.user},
            )
            if created:
                self._record_audit("INSERT", reminder)
                logs = OutboxService(user=self.user).create_event_deliveries(
                    source_type="enrollment_reminder",
                    source_id=str(reminder.pk),
                    recipient=user,
                    event="document_action",
                    action_url=reverse("service_request_create"),
                    scope={"student_ids": [str(application.student_id)]},
                )
                email = next(log for log in logs if log.channel == "EMAIL")
            elif reminder.status in {"FAILED", "SKIPPED"}:
                email = OutboxService(user=self.user).request_delivery_retry(
                    reminder.message_log_id
                )
                reminder.refresh_from_db()
            else:
                continue
            reminder.message_log_id = email.pk
            reminder.status = "PENDING"
            reminder.save()
            self._record_audit("UPDATE", reminder)
            DeliveryProjectionService().synchronize_delivery(email)
            results.append(reminder)
        self._log(
            "enrollment_reminders_persisted", application_id=str(application.pk), count=len(results)
        )
        return results
