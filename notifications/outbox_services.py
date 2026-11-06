"""Intenções persistidas antes da fila e entrega com lease e fencing."""

import uuid
from datetime import timedelta
from urllib.parse import urlsplit

from django.utils import timezone

from base.context import active_tenant_schema
from base.events import publish_task_after_commit
from base.exceptions import (
    ValidationError,
)
from base.services import BaseService, system_command
from notifications.models import MessageLog
from notifications.outbox_reprocessing_services import OutboxReprocessingMixin
from notifications.outbox_selectors import EVENT_MESSAGES, OutboxSelector


class OutboxService(OutboxReprocessingMixin, BaseService):
    @system_command
    def create_event_deliveries(
        self,
        *,
        source_type,
        source_id,
        recipient,
        action_url,
        event,
        send_email=True,
        announcement_recipient=None,
        diary_publication_id=None,
        event_version="",
        inbox=True,
        scope=None,
    ):
        """Contrato interno: produtor autorizado grava intenção no próprio commit."""
        schema = active_tenant_schema()
        if event not in EVENT_MESSAGES:
            raise ValidationError(errors={"event": ["Evento de comunicação desconhecido."]})
        parts = urlsplit(action_url)
        path = parts.path + ("?" + parts.query if parts.query else "")
        if not path.startswith("/") or path.startswith("//"):
            raise ValidationError(errors={"action_url": ["Informe uma rota interna."]})
        logs = []
        for channel in (["IN_APP"] if inbox else []) + (["EMAIL"] if send_email else []):
            recipient_key = recipient.pk if recipient else "contact"
            key = f"{source_type}:{source_id}:{event}:{event_version}:{recipient_key}:{channel}"
            delivery, created = MessageLog.objects.get_or_create(
                dedupe_key=key,
                defaults={
                    "source_type": source_type,
                    "source_id": source_id,
                    "recipient": recipient,
                    "announcement_recipient": announcement_recipient,
                    "announcement": (
                        announcement_recipient.revision.announcement
                        if announcement_recipient
                        else None
                    ),
                    "diary_publication_id": diary_publication_id,
                    "channel": channel,
                    "recipient_address": "",
                    "payload": {"event": event, "action_url": path, "scope": scope or {}},
                    "created_by": self.user,
                    "updated_by": self.user,
                },
            )
            if created:
                self._record_audit("INSERT", delivery)
                if channel == "IN_APP" and recipient and recipient.is_active:
                    self._create_inbox(delivery, recipient)
                else:
                    from notifications.outbox_tasks import deliver_outbox_task

                    publish_task_after_commit(
                        deliver_outbox_task, schema, str(delivery.pk), tenant_schema=schema
                    )
            logs.append(delivery)
        self._log(
            "outbox_intentions_persisted",
            count=len(logs),
            source_type=source_type,
            source_id=source_id,
        )
        return logs

    def _create_inbox(self, delivery, user):
        from notifications.services import NotificationService

        title, message = EVENT_MESSAGES[delivery.payload["event"]]
        notification = NotificationService(user=self.user).create_notification(
            {
                "recipient_id": user.pk,
                "title": title,
                "message": message,
                "source": delivery.source_type,
                "action_url": delivery.payload["action_url"],
            }
        )
        delivery.notification = notification
        delivery.recipient = user
        delivery.dispatch_state = MessageLog.DispatchState.COMPLETE
        delivery.status = MessageLog.Status.DELIVERED
        delivery.delivered_at = timezone.now()
        delivery.lease_until = None
        self._persist(delivery)
        return notification

    @system_command
    def claim_delivery(self, delivery_id):
        from notifications.task_helpers import get_transport
        from tenancy.selectors import SchoolSelector

        active_tenant_schema()
        delivery = (
            MessageLog.objects.select_for_update(of=("self",))
            .select_related(
                "recipient__role",
                "announcement_recipient__guardian__user__role",
                "announcement_recipient__user__role",
            )
            .get(pk=delivery_id)
        )
        now = timezone.now()
        if OutboxSelector.previous_delivery_succeeded(delivery):
            self._skip(delivery, "previous_delivery_succeeded")
            return None
        if delivery.dispatch_state not in {"PENDING", "RETRY", "PROCESSING"}:
            return None
        if delivery.lease_until and delivery.lease_until > now:
            return None
        if delivery.next_attempt_at and delivery.next_attempt_at > now:
            return None
        if delivery.status == "FAILED":
            self._skip(delivery, "provider_failure", failed=True)
            return None
        if delivery.status in {
            "SENT",
            "DELIVERED",
            "DELAYED",
            "BOUNCED",
            "SUPPRESSED",
            "COMPLAINED",
        }:
            delivery.dispatch_state = "COMPLETE"
            self._persist(delivery)
            return None
        user, reason = OutboxSelector.eligible_recipient(delivery)
        if reason:
            self._skip(delivery, reason, revoked=reason != "account_not_activated")
            return None
        if delivery.channel == "IN_APP":
            self._create_inbox(delivery, user)
            return None
        transport = get_transport("EMAIL")
        if not user.email:
            self._skip(delivery, "address_missing")
            return None
        if delivery.source_type != "account_invitation" and not transport._allows_channel(user):
            self._skip(delivery, "preference_disabled")
            return None
        if delivery.payload.get("url") and delivery.recipient_address != user.email:
            self._skip(delivery, "recipient_address_changed", revoked=True)
            return None
        if delivery.attempts >= 3:
            self._skip(delivery, "attempts_exhausted", failed=True)
            return None
        if not delivery.payload.get("url"):
            school = SchoolSelector().get_active_by_schema(active_tenant_schema())
            domain = school.domains.filter(is_primary=True).first()
            if not domain:
                self._skip(delivery, "school_domain_missing", failed=True)
                return None
            from core.tenant_urls import school_url

            title, generic = EVENT_MESSAGES[delivery.payload["event"]]
            if delivery.source_type == "account_invitation":
                from zoneinfo import ZoneInfo

                expiry = user.invitation_expires_at.astimezone(ZoneInfo("America/Sao_Paulo"))
                generic += f" Válido até {expiry:%d/%m/%Y às %H:%M} (horário de Brasília)."
            from core.tenant_email import get_tenant_resend_config

            config = get_tenant_resend_config()
            sender_name = config["school_name"].strip()
            sender_email = config["from_email"].strip()
            sender = f"{sender_name} <{sender_email}>" if sender_name else sender_email
            delivery.payload = {
                **delivery.payload,
                "subject": title,
                "school": school.name,
                "generic": generic,
                "sender_address": sender,
                "url": school_url(school, delivery.payload["action_url"]),
            }
            delivery.recipient_address = user.email
            delivery.recipient = user
        delivery.dispatch_state = "PROCESSING"
        delivery.lease_token = uuid.uuid4()
        delivery.lease_until = now + timedelta(minutes=3)
        delivery.attempts += 1
        delivery.reason_code = ""
        delivery.save()
        self._record_audit(
            "UPDATE",
            delivery,
            new_values={"dispatch_state": delivery.dispatch_state, "payload": delivery.payload},
        )
        self._log(
            "outbox_delivery_claimed", message_log_id=str(delivery.pk), attempts=delivery.attempts
        )
        return delivery

    def dispatch(self, delivery_id):
        """Rede fora da transação; a mesma chave e payload sobrevivem à queda do worker."""
        from notifications.channels import ChannelResult
        from notifications.task_helpers import get_transport

        delivery = self.claim_delivery(delivery_id)
        if delivery is None:
            return
        if OutboxSelector.previous_delivery_succeeded(delivery):
            self.finish_revoked(delivery.pk, delivery.lease_token, "previous_delivery_succeeded")
            return
        user, reason = OutboxSelector.eligible_recipient(delivery)
        if reason:
            self.finish_revoked(delivery.pk, delivery.lease_token, reason)
            return
        if user.email != delivery.recipient_address:
            self.finish_revoked(delivery.pk, delivery.lease_token, "recipient_address_changed")
            return
        if delivery.source_type != "account_invitation" and not get_transport(
            "EMAIL"
        )._allows_channel(user):
            self.finish_revoked(delivery.pk, delivery.lease_token, "preference_disabled")
            return
        payload = delivery.payload
        action_url = payload["url"]
        if delivery.source_type == "account_invitation":
            from accounts.invitation_selectors import InvitationSelector

            action_url = InvitationSelector.transport_url(delivery)
        try:
            result = get_transport("EMAIL").channel.send(
                delivery.recipient_address,
                payload["subject"],
                f'{payload["school"]}\n\n{payload["generic"]}\n\n{action_url}',
                tenant_schema=active_tenant_schema(),
                message_log_id=str(delivery.pk),
                idempotency_key=f"message-log/{delivery.pk}",
                category=delivery.source_type,
                action_url=action_url,
                school_name=payload["school"],
                generic_message=payload["generic"],
                expected_sender=payload["sender_address"],
            )
        except Exception:
            result = ChannelResult(
                success=False,
                channel="EMAIL",
                recipient_address="",
                error_message="provider_unavailable",
                retryable=True,
            )
        self.finish_delivery(delivery.pk, delivery.lease_token, result)

    @system_command
    def finish_delivery(self, delivery_id, lease_token, result):
        from notifications.delivery_services import MessageDeliveryService

        delivery = MessageLog.objects.select_for_update().get(pk=delivery_id)
        if delivery.lease_token != lease_token or delivery.dispatch_state != "PROCESSING":
            return
        MessageDeliveryService().record_channel_result(delivery.pk, result)
        delivery.refresh_from_db()
        if delivery.status in {
            "SENT",
            "DELIVERED",
            "DELAYED",
            "BOUNCED",
            "SUPPRESSED",
            "COMPLAINED",
        }:
            delivery.dispatch_state = "COMPLETE"
            delivery.reason_code = ""
        elif delivery.status == "FAILED":
            delivery.dispatch_state = "FAILED"
            delivery.reason_code = "provider_failure"
        elif result.retryable and delivery.attempts < 3:
            delivery.dispatch_state = "RETRY"
            delivery.reason_code = "transient_failure"
            delivery.next_attempt_at = timezone.now() + timedelta(
                seconds=60 * 2 ** (delivery.attempts - 1)
            )
        else:
            delivery.dispatch_state = "FAILED"
            delivery.reason_code = "attempts_exhausted" if result.retryable else "permanent_failure"
        delivery.lease_until = None
        self._persist(delivery)
        self._log(
            "outbox_delivery_finished",
            message_log_id=str(delivery.pk),
            state=delivery.dispatch_state,
        )

    @system_command
    def finish_revoked(self, delivery_id, lease_token, reason):
        delivery = MessageLog.objects.select_for_update().get(pk=delivery_id)
        if delivery.lease_token == lease_token:
            self._skip(delivery, reason, revoked=True)

    def _skip(self, delivery, reason, *, revoked=False, failed=False):
        delivery.dispatch_state = "REVOKED" if revoked else "FAILED" if failed else "SKIPPED"
        delivery.reason_code = reason
        delivery.lease_until = None
        self._persist(delivery)
        self._log("outbox_delivery_not_sent", message_log_id=str(delivery.pk), reason_code=reason)

    def _persist(self, delivery):
        from notifications.projection_services import DeliveryProjectionService

        delivery.save()
        self._record_audit("UPDATE", delivery)
        DeliveryProjectionService().synchronize_delivery(delivery)
