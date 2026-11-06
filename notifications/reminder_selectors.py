"""Elegibilidade de lembretes de negócio no único worker de comunicação."""

from core.permissions import can_access


class ReminderDeliverySelector:
    @staticmethod
    def eligible(delivery, user):
        from guardians.selectors import GuardianSelector

        if not user or not user.is_active or user.deleted_at:
            return False
        if delivery.source_type == "enrollment_reminder":
            from enrollments.contracts import EnrollmentReminder, StudentDocument
            from enrollments.selectors import EnrollmentApplicationSelector

            item = (
                EnrollmentReminder.objects.select_related("application")
                .filter(pk=delivery.source_id)
                .first()
            )
            return bool(
                item
                and item.application.status not in {"ENROLLED", "CANCELLED", "REJECTED"}
                and EnrollmentApplicationSelector().is_reminder_recipient_eligible(
                    item.application_id, user.pk
                )
                and StudentDocument.objects.filter(application=item.application, is_required=True)
                .exclude(status__in=["VERIFIED", "WAIVED"])
                .exists()
            )
        from financeiro.contracts import CollectionReminder

        item = (
            CollectionReminder.objects.select_related("billing")
            .filter(pk=delivery.source_id)
            .first()
        )
        return bool(
            item
            and item.recipient_id == user.pk
            and item.billing.status == "ACTIVE"
            and item.billing.outstanding_value > 0
            and can_access(user, "finance_billings", "view")
            and GuardianSelector()
            .custodial_links_for_user(user.pk)
            .filter(student_id=item.billing.student_id, guardian_id=item.guardian_id)
            .exists()
        )

    @staticmethod
    def can_reprocess(delivery, user):
        module = (
            "enrollments" if delivery.source_type == "enrollment_reminder" else "finance_reminders"
        )
        return can_access(user, module, "edit")
