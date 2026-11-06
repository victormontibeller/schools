"""Revalidação imediata do vínculo e da responsabilidade por aviso de atendimento."""

from core.permissions import role_name
from service_requests.models import ServiceRequest
from service_requests.selectors import ServiceRequestSelector, is_administrator


class RequestDeliverySelector:
    @staticmethod
    def eligible(delivery, user):
        ticket = (
            ServiceRequest.objects.select_related("department")
            .filter(pk=delivery.source_id)
            .first()
        )
        if not ticket or not ServiceRequestSelector.can_read(ticket, user):
            return False
        scope = delivery.payload.get("scope", {})
        if user.pk != ticket.author_id and not is_administrator(user):
            if scope.get("department_id") != str(ticket.department_id):
                return False
        if delivery.payload["event"] == "request_overdue":
            if (
                user.pk == ticket.author_id
                or ticket.first_response_at
                or ticket.cycle != scope.get("cycle")
                or ticket.status in {"RESOLVED", "CANCELLED"}
            ):
                return False
        return True

    @staticmethod
    def can_reprocess(delivery, user):
        ticket = ServiceRequest.objects.filter(pk=delivery.source_id).first()
        return bool(
            ticket
            and role_name(user) != "GUARDIAN"
            and ServiceRequestSelector.can_respond(ticket, user)
            and RequestDeliverySelector.eligible(delivery, user)
        )
