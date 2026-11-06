"""Sinais operacionais agregados sem conteúdo escolar ou identificadores pessoais."""

from django.db.models import Min
from django.utils import timezone

from base.context import tenant_schema_context


class OperationsSelector:
    @staticmethod
    def communication_health(maximum_age_seconds=300):
        from notifications.contracts import MessageLog
        from tenancy.selectors import SchoolSelector

        count, overdue = 0, 0
        for schema in SchoolSelector().list_active_schemas():
            with tenant_schema_context(schema):
                query = MessageLog.objects.filter(
                    dispatch_state__in=["PENDING", "RETRY", "PROCESSING"], dedupe_key__isnull=False
                )
                count += query.count()
                oldest = query.aggregate(oldest=Min("created_at"))["oldest"]
                if oldest and (timezone.now() - oldest).total_seconds() > maximum_age_seconds:
                    overdue += 1
        return {"pending_deliveries": count, "schools_with_overdue_outbox": overdue}
