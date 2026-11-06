"""Projeções operacionais dos lembretes, sem segundo mecanismo de entrega."""

from base.services import BaseService, system_command
from notifications.models import MessageLog


class DeliveryProjectionService(BaseService):
    @system_command
    def synchronize_delivery(self, delivery):
        if delivery.source_type == "enrollment_reminder":
            from enrollments.contracts import EnrollmentReminder

            item = (
                EnrollmentReminder.objects.select_for_update().filter(pk=delivery.source_id).first()
            )
        elif delivery.source_type == "financial_reminder":
            from financeiro.contracts import CollectionReminder

            item = (
                CollectionReminder.objects.select_for_update().filter(pk=delivery.source_id).first()
            )
        else:
            return
        if not item or str(item.message_log_id) != str(delivery.pk):
            return
        if delivery.status in {
            MessageLog.Status.SENT,
            MessageLog.Status.DELIVERED,
            MessageLog.Status.DELAYED,
        }:
            status = "SENT"
        elif delivery.dispatch_state in {"FAILED", "SKIPPED", "REVOKED"}:
            status = "SKIPPED" if delivery.dispatch_state in {"SKIPPED", "REVOKED"} else "FAILED"
        else:
            status = "PENDING"
        if item.status == status:
            return
        old = {"status": item.status}
        item.status = status
        item.sent_at = delivery.sent_at or delivery.delivered_at if status == "SENT" else None
        if delivery.source_type == "financial_reminder":
            item.error_code = delivery.reason_code
        item.save()
        self._record_audit("UPDATE", item, old_values=old)
        self._log(
            "reminder_delivery_projected",
            source_type=delivery.source_type,
            source_id=str(item.pk),
            status=status,
        )

    @system_command
    def attach_successor(self, delivery):
        if delivery.source_type == "enrollment_reminder":
            from enrollments.contracts import EnrollmentReminder

            model = EnrollmentReminder
        elif delivery.source_type == "financial_reminder":
            from financeiro.contracts import CollectionReminder

            model = CollectionReminder
        else:
            return
        item = model.objects.select_for_update().get(pk=delivery.source_id)
        if str(item.message_log_id) != str(delivery.previous_delivery_id):
            return
        item.message_log_id = delivery.pk
        item.status = "PENDING"
        item.sent_at = None
        item.save()
        self._record_audit("UPDATE", item)
        self._log(
            "reminder_successor_attached", source_id=str(item.pk), source_type=delivery.source_type
        )
