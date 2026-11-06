"""Avisos duráveis do atendimento sem conteúdo pessoal no e-mail."""

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from base.services import BaseService, system_command
from notifications.outbox_services import OutboxService
from service_requests.models import ServiceRequest
from service_requests.selectors import ServiceRequestSelector, ServiceStaffSelector


class RequestEventService(BaseService):
    @system_command
    def emit_request_event(self, ticket, event, identity, *, to_author=None):
        from core.contracts import CustomUser

        recipients = {}
        if to_author is not True:
            recipients = {u.pk: u for u in ServiceStaffSelector.attendants(ticket.department)}
        if event == "request_overdue":
            recipients.update(
                {
                    u.pk: u
                    for u in CustomUser.objects.filter(
                        Q(role__name="ADMIN") | Q(is_superuser=True), is_active=True
                    )
                }
            )
        elif to_author is not False:
            recipients[ticket.author_id] = ticket.author
        for user in recipients.values():
            OutboxService(user=self.user).create_event_deliveries(
                source_type="service_requests",
                source_id=str(ticket.pk),
                recipient=user,
                action_url=reverse("service_request_detail", args=[ticket.pk]),
                event=event,
                event_version=f"{ticket.cycle}:{identity}:{ticket.department_id}",
                scope={"department_id": str(ticket.department_id), "cycle": ticket.cycle},
            )

    @system_command
    def notify_overdue_request(self, pk):
        ServiceRequestSelector.assert_school_active()
        ticket = ServiceRequest.objects.select_for_update().get(pk=pk)
        if (
            ticket.first_response_at
            or ticket.response_due_at >= timezone.now()
            or ticket.status in {"RESOLVED", "CANCELLED"}
            or ticket.overdue_notified_cycle == ticket.cycle
        ):
            return
        ticket.overdue_notified_cycle = ticket.cycle
        ticket.save()
        self._record_audit("UPDATE", ticket)
        self.emit_request_event(ticket, "request_overdue", str(ticket.cycle), to_author=False)
        self._log("service_request_overdue_notified", request_id=str(ticket.pk), cycle=ticket.cycle)
