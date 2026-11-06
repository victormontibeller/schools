"""Nova geração auditada de entrega após correção humana da causa."""

from base.context import active_tenant_schema
from base.events import publish_task_after_commit
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, PermissionDeniedError
from notifications.models import MessageLog
from notifications.outbox_selectors import OutboxSelector


class OutboxReprocessingMixin:
    def request_delivery_retry(self, delivery_id):
        """Nova geração humana após correção; retentativas técnicas não passam aqui."""
        from notifications.outbox_tasks import deliver_outbox_task
        from notifications.task_helpers import get_transport

        schema = active_tenant_schema()
        try:
            previous = MessageLog.objects.select_for_update().get(pk=delivery_id)
        except MessageLog.DoesNotExist:
            raise ObjectNotFoundError("MessageLog", str(delivery_id)) from None
        if not OutboxSelector.can_reprocess(previous, self.user):
            raise PermissionDeniedError("Sem permissão para reprocessar esta entrega.")
        allowed = previous.dispatch_state in {
            "FAILED",
            "SKIPPED",
            "REVOKED",
        } or previous.status in {"FAILED", "BOUNCED", "SUPPRESSED"}
        if not allowed:
            raise BusinessRuleViolationError(
                "Somente entregas não concluídas podem ser reprocessadas."
            )
        successor = MessageLog.objects.filter(previous_delivery=previous).first()
        if successor:
            return successor
        user, reason = OutboxSelector.eligible_recipient(previous)
        if reason or not user:
            raise BusinessRuleViolationError("Corrija a elegibilidade antes do reprocessamento.")
        if previous.channel == "EMAIL" and (
            not user.email
            or (
                previous.source_type != "account_invitation"
                and not get_transport("EMAIL")._allows_channel(user)
            )
        ):
            raise BusinessRuleViolationError(
                "Corrija o endereço ou aguarde a preferência da pessoa antes do reprocessamento."
            )
        delivery = MessageLog.objects.create(
            previous_delivery=previous,
            generation=previous.generation + 1,
            dedupe_key=f"reprocess:{previous.pk}:{previous.channel}",
            source_type=previous.source_type,
            source_id=previous.source_id,
            recipient=user,
            announcement_recipient=previous.announcement_recipient,
            announcement=previous.announcement,
            diary_publication=previous.diary_publication,
            channel=previous.channel,
            recipient_address="",
            payload={key: previous.payload.get(key) for key in ("event", "action_url", "scope")},
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", delivery)
        from notifications.projection_services import DeliveryProjectionService

        DeliveryProjectionService().attach_successor(delivery)
        self._log(
            "outbox_delivery_reprocess_requested",
            message_log_id=str(delivery.pk),
            previous_id=str(previous.pk),
        )
        publish_task_after_commit(
            deliver_outbox_task, schema, str(delivery.pk), tenant_schema=schema
        )
        return delivery
