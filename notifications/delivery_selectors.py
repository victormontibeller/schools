"""Painel operacional de falhas restrito às capacidades de cada domínio."""

from django.db.models import Q
from django.urls import reverse

from base.selectors import PageResult
from notifications.models import MessageLog
from notifications.outbox_selectors import OutboxSelector


class CommunicationDeliverySelector:
    def list_for_user(self, user, page=1, search=""):
        from core.contracts import CustomUser

        user = CustomUser.objects.select_related("role").get(pk=user.pk)
        query = (
            MessageLog.objects.filter(dedupe_key__isnull=False)
            .select_related("recipient")
            .order_by("-created_at")
        )
        if search:
            query = query.filter(
                Q(recipient__first_name__icontains=search)
                | Q(recipient__last_name__icontains=search)
                | Q(reason_code__icontains=search)
            )
        ids = [log.pk for log in query if OutboxSelector.can_reprocess(log, user)]
        page = max(1, int(page))
        visible = query.filter(pk__in=ids)
        items = list(visible[(page - 1) * 20 : page * 20])
        for item in items:
            item.management_url = self.management_url(item)
        return PageResult(
            items=items,
            total=len(ids),
            page=page,
            page_size=20,
        )

    @staticmethod
    def management_url(item):
        if item.announcement_id:
            return reverse("announcement_detail", args=[item.announcement_id])
        if item.source_type == "account_invitation":
            return reverse("user_detail", args=[item.source_id])
        routes = {
            "activity": "activity_detail",
            "calendar_event": "event_detail",
            "enrollment_application": "enrollment_application_detail",
            "payment": "payment_detail",
            "service_requests": "service_request_detail",
        }
        if item.source_type in routes:
            return reverse(routes[item.source_type], args=[item.source_id])
        if item.source_type == "enrollment_reminder":
            from enrollments.contracts import EnrollmentReminder

            reminder = EnrollmentReminder.objects.filter(pk=item.source_id).first()
            if reminder:
                return reverse("enrollment_application_detail", args=[reminder.application_id])
        return reverse(
            {"student_diary": "diary_daily", "financial_reminder": "finance_dashboard"}.get(
                item.source_type, "communication_delivery_list"
            )
        )
