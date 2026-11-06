"""Comandos da régua de cobrança e das entregas deduplicadas."""

from __future__ import annotations

import datetime as dt

from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import service_command, system_command


class ReminderLifecycleMixin:
    """Configura a política e enfileira lembretes sem enviar dentro da transação."""

    @service_command
    def configure_reminder_policy(self, data: dict):
        from financeiro.models import CollectionReminderPolicy

        offsets = sorted({int(value) for value in data.get("offset_days", [])})
        channels = list(dict.fromkeys(data.get("channels", [])))
        allowed_channels = {"IN_APP", "EMAIL"}
        if set(channels) - allowed_channels:
            raise ValidationError(errors={"channels": ["Canal indisponível para esta escola."]})
        if data.get("enabled") and (not offsets or not channels):
            raise BusinessRuleViolationError(
                "A régua exige ao menos uma regra e um canal antes da ativação."
            )
        if any(value < -365 or value > 365 for value in offsets):
            raise ValidationError(errors={"offset_days": ["Use valores entre -365 e 365."]})
        policy = CollectionReminderPolicy.objects.select_for_update().first()
        old = None
        if policy is None:
            policy = CollectionReminderPolicy(created_by=self.user)
        else:
            old = self._snapshot(policy, ["name", "enabled", "offset_days", "channels"])
        policy.name = data.get("name", "Régua principal").strip() or "Régua principal"
        policy.enabled = bool(data.get("enabled", False))
        policy.offset_days = offsets
        policy.channels = channels
        policy.updated_by = self.user
        policy.save()
        self._record_audit("INSERT" if old is None else "UPDATE", policy, old_values=old)
        self._log(
            "collection_policy_saved",
            policy_id=str(policy.pk),
            enabled=policy.enabled,
            rule_count=len(offsets),
            channel_count=len(channels),
        )
        return policy

    @service_command
    def send_manual_reminder(self, billing_id, *, channels=None) -> int:
        """Enfileira lembretes manuais usando a mesma validação do agendamento."""
        from financeiro.models import BillingEntry

        try:
            billing = BillingEntry.objects.get(pk=billing_id)
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None
        if billing.status == BillingEntry.Status.CANCELLED or billing.outstanding_value <= 0:
            return 0
        selected = channels or ["IN_APP"]
        return self._enqueue_for_billing(
            billing,
            reference_date=timezone.localdate(),
            rule_offset_days=0,
            channels=selected,
        )

    @system_command
    def run_scheduled_reminders(self, *, reference_date=None) -> int:
        """Materializa somente regras que vencem na data da execução."""
        from base.context import active_tenant_schema
        from financeiro.models import BillingEntry, CollectionReminderPolicy
        from tenancy.selectors import SchoolSelector

        SchoolSelector().get_active_by_schema(active_tenant_schema())
        reference = reference_date or timezone.localdate()
        policy = CollectionReminderPolicy.objects.filter(enabled=True).first()
        if policy is None or not policy.offset_days or not policy.channels:
            return 0
        total = 0
        for offset in policy.offset_days:
            due_date = reference - dt.timedelta(days=int(offset))
            billings = BillingEntry.objects.filter(due_date=due_date).exclude(
                status=BillingEntry.Status.CANCELLED
            )
            for billing in billings.iterator():
                if billing.outstanding_value <= 0:
                    continue
                total += self._enqueue_for_billing(
                    billing,
                    reference_date=reference,
                    rule_offset_days=int(offset),
                    channels=policy.channels,
                )
        return total

    def _enqueue_for_billing(
        self,
        billing,
        *,
        reference_date: dt.date,
        rule_offset_days: int,
        channels: list[str],
    ) -> int:
        from core.access_catalog import FINANCE_BILLINGS, VIEW
        from core.permissions import can_access
        from financeiro.models import CollectionReminder
        from guardians.selectors import GuardianSelector

        relations = GuardianSelector().custodial_links_for_students([billing.student_id])
        created_ids = []
        for relation in relations:
            guardian = relation.guardian
            if not can_access(guardian.user, FINANCE_BILLINGS, VIEW):
                continue
            for channel in channels:
                if not self._guardian_allows_channel(guardian, channel):
                    continue
                reminder, created = CollectionReminder.objects.get_or_create(
                    billing=billing,
                    guardian=guardian,
                    recipient=guardian.user,
                    channel=channel,
                    rule_offset_days=rule_offset_days,
                    scheduled_for=reference_date,
                    defaults={"created_by": self.user, "updated_by": self.user},
                )
                if created:
                    self._record_audit("INSERT", reminder)
                    from django.urls import reverse

                    from notifications.outbox_services import OutboxService
                    from notifications.projection_services import DeliveryProjectionService

                    logs = OutboxService(user=self.user).create_event_deliveries(
                        source_type="financial_reminder",
                        source_id=str(reminder.pk),
                        recipient=guardian.user,
                        event="financial_reminder",
                        action_url=reverse("billing_detail", args=[billing.pk]),
                        send_email=channel == "EMAIL",
                        inbox=channel == "IN_APP",
                        scope={"student_ids": [str(billing.student_id)]},
                    )
                    reminder.message_log_id = logs[0].pk
                    reminder.save()
                    self._record_audit("UPDATE", reminder)
                    DeliveryProjectionService().synchronize_delivery(logs[0])
                    created_ids.append(str(reminder.pk))
        self._log(
            "collection_reminders_enqueued",
            billing_id=str(billing.pk),
            created_count=len(created_ids),
        )
        return len(created_ids)

    @staticmethod
    def _guardian_allows_channel(guardian, channel: str) -> bool:
        if channel == "IN_APP":
            return guardian.user_id is not None
        if channel == "EMAIL":
            return bool(guardian.user_id and guardian.accepts_email_notifications)
        return False
