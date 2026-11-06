"""Materialização atômica de avisos escolares sem dependência de login infantil."""

from django.urls import reverse

from base.services import BaseService, system_command
from notifications.domain_event_selectors import DomainEventAudience
from notifications.outbox_services import OutboxService


class DomainCommunicationService(BaseService):
    @system_command
    def emit_domain_event(self, instance, kind):
        rows = []
        source = ""
        if kind == "activity_published":
            source = "activity"
            rows = DomainEventAudience.family_rows(
                DomainEventAudience.class_student_ids(instance.class_obj_id)
            )
            path = reverse("activity_detail", args=[instance.pk])
        elif kind == "calendar_published":
            source = "calendar_event"
            if instance.is_cancelled or (
                instance.audience == "CLASS" and not instance.class_obj_id
            ):
                return
            if instance.is_public and instance.audience in {"ALL", "GUARDIANS", "CLASS"}:
                rows = DomainEventAudience.family_rows(
                    DomainEventAudience.class_student_ids(
                        instance.class_obj_id if instance.audience == "CLASS" else None
                    )
                )
            if instance.audience in {"ALL", "TEACHERS"}:
                rows += [
                    {"user": u, "student_ids": []}
                    for u in DomainEventAudience.staff_calendar_users()
                ]
            path = reverse("event_detail", args=[instance.pk])
        elif kind in {"enrollment_confirmed", "document_action"}:
            source = "enrollment_application"
            rows = DomainEventAudience.family_rows([instance.student_id], primary=True)
            path = (
                reverse("student_profile", args=[instance.student_id])
                if kind == "enrollment_confirmed"
                else reverse("service_request_create")
            )
        elif kind in {"payment_confirmed", "payment_reversed"}:
            source = "payment"
            student_ids = instance.allocations.values_list("billing__student_id", flat=True)
            rows = DomainEventAudience.family_rows(student_ids, financial=True)
            path = reverse("billing_list")
        else:
            return
        for row in rows:
            OutboxService(user=self.user).create_event_deliveries(
                source_type=source,
                source_id=str(instance.pk),
                recipient=row["user"],
                action_url=path,
                event=kind,
                event_version=str(instance.version),
                scope={"student_ids": row["student_ids"]},
            )
        self._log(
            "domain_communications_persisted",
            source_type=source,
            source_id=str(instance.pk),
            count=len(rows),
        )
