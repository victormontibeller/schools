"""Elegibilidade vigente dos eventos duráveis de comunicação."""

from django.db.models import Q
from django.utils import timezone

from base.context import active_tenant_schema
from base.exceptions import ObjectNotFoundError, PermissionDeniedError
from notifications.models import MessageLog

EVENT_MESSAGES = {
    "account_invitation": (
        "Ative seu acesso à escola",
        "Você recebeu acesso à escola. Defina sua senha antes do vencimento indicado.",
    ),
    "financial_reminder": (
        "Atualização financeira disponível",
        "Há uma atualização financeira disponível. Acesse sua conta para consultar.",
    ),
    "activity_published": (
        "Nova atividade da escola",
        "Há uma atividade publicada para a família. Acesse sua conta para consultar.",
    ),
    "calendar_published": (
        "Evento da escola disponível",
        "Há uma atualização no calendário escolar. Acesse sua conta para consultar.",
    ),
    "enrollment_confirmed": (
        "Matrícula efetivada",
        "A matrícula foi efetivada. Acesse sua conta para acompanhar.",
    ),
    "document_action": (
        "Ação documental necessária",
        "Há uma pendência documental. Acesse sua conta e contate a Secretaria para orientações.",
    ),
    "payment_confirmed": (
        "Baixa confirmada",
        "Há uma confirmação financeira disponível. Acesse sua conta para consultar o recibo.",
    ),
    "payment_reversed": (
        "Atualização de pagamento",
        "Há uma atualização financeira disponível. Acesse sua conta para consultar.",
    ),
    "request_opened": (
        "Solicitação registrada",
        "Sua solicitação foi registrada. Acesse sua conta para consultar protocolo e prazo.",
    ),
    "request_response": (
        "Resposta na solicitação",
        "Sua solicitação recebeu uma resposta. Acesse sua conta para acompanhar.",
    ),
    "request_reopened": (
        "Solicitação reaberta",
        "Uma solicitação foi reaberta. Acesse sua conta para acompanhar o novo prazo.",
    ),
    "request_transferred": (
        "Solicitação encaminhada",
        "Há uma solicitação encaminhada ao seu setor. Acesse sua conta para atender.",
    ),
    "request_overdue": (
        "Solicitação com prazo vencido",
        "Há uma solicitação com prazo de resposta vencido. Acesse sua conta para atender.",
    ),
    "announcement": (
        "Novo comunicado da escola",
        "Há um novo comunicado da escola. Acesse sua conta para consultar.",
    ),
    "publication": (
        "Rotina escolar atualizada",
        "A rotina escolar foi atualizada. Entre no School Manager para visualizar.",
    ),
    "review_requested": (
        "Agenda aguardando revisão",
        "Uma agenda foi enviada para revisão. Acesse sua conta para acompanhar.",
    ),
    "changes_requested": (
        "Correção solicitada na Agenda",
        "Uma agenda foi devolvida para correção. Acesse sua conta para acompanhar.",
    ),
}


class OutboxSelector:
    @staticmethod
    def can_reprocess(delivery, user):
        from core.contracts import CustomUser
        from core.permissions import can_access

        user = (
            CustomUser.objects.select_related("role").filter(pk=getattr(user, "pk", None)).first()
        )
        if not user or not user.is_active or not can_access(user, "communication_delivery", "edit"):
            return False
        if delivery.source_type == "account_invitation":
            kind = delivery.payload.get("scope", {}).get("invitation_kind")
            return can_access(
                user,
                {"staff": "__admin__", "teacher": "teachers", "guardian": "guardians"}.get(
                    kind, ""
                ),
                "edit",
            )
        if delivery.announcement_recipient_id:
            from notifications.announcement_selectors import can_manage_announcements

            return can_manage_announcements(user, "edit")
        if delivery.source_type == "student_diary":
            from core.permissions import can_access, role_name

            return role_name(user) in {"ADMIN", "COORDINATOR"} and can_access(
                user, "student_diary", "edit"
            )
        if delivery.source_type in {
            "activity",
            "calendar_event",
            "enrollment_application",
            "payment",
        }:
            from core.permissions import can_access

            module = {
                "activity": "activities",
                "calendar_event": "academic_calendar",
                "enrollment_application": "enrollments",
                "payment": "finance_payments",
            }[delivery.source_type]
            return can_access(user, module, "edit")
        if delivery.source_type in {"enrollment_reminder", "financial_reminder"}:
            from notifications.reminder_selectors import ReminderDeliverySelector

            return ReminderDeliverySelector.can_reprocess(delivery, user)
        if delivery.source_type == "service_requests":
            from service_requests.delivery_selectors import RequestDeliverySelector

            return RequestDeliverySelector.can_reprocess(delivery, user)
        return False

    @staticmethod
    def previous_delivery_succeeded(delivery):
        """Uma confirmação tardia de qualquer geração impede novos envios."""
        previous_id = delivery.previous_delivery_id
        while previous_id:
            previous_id, status = MessageLog.objects.values_list(
                "previous_delivery_id", "status"
            ).get(pk=previous_id)
            if status in {"SENT", "DELIVERED", "DELAYED"}:
                return True
        return False

    @staticmethod
    def pending_ids(limit=100):
        now = timezone.now()
        return (
            MessageLog.objects.filter(dedupe_key__isnull=False)
            .filter(
                Q(dispatch_state__in=["PENDING", "RETRY"])
                & (Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
                | Q(dispatch_state="PROCESSING", lease_until__lte=now)
            )
            .order_by("created_at")
            .values_list("pk", flat=True)[:limit]
        )

    @staticmethod
    def eligible_recipient(delivery):
        from notifications.announcement_selectors import AnnouncementAudienceSelector
        from tenancy.selectors import SchoolSelector

        try:
            SchoolSelector().get_active_by_schema(active_tenant_schema())
        except ObjectNotFoundError:
            return None, "school_inactive"
        from core.contracts import CustomUser

        user = CustomUser.objects.select_related("role").filter(pk=delivery.recipient_id).first()
        if delivery.source_type == "account_invitation":
            from accounts.invitation_selectors import InvitationSelector

            scope = delivery.payload.get("scope", {})
            if not InvitationSelector.is_current_token(
                user,
                scope.get("invitation_token"),
                schema=active_tenant_schema(),
                kind=scope.get("invitation_kind"),
            ):
                return None, "access_revoked"
        elif delivery.announcement_recipient_id:
            receipt = delivery.announcement_recipient
            user = AnnouncementAudienceSelector.current_user(receipt)
            if receipt.guardian_id:
                from guardians.contracts import StudentGuardian

                if not StudentGuardian.objects.filter(
                    guardian_id=receipt.guardian_id,
                    guardian__is_active=True,
                    guardian__deleted_at__isnull=True,
                    student_id__in=receipt.student_ids,
                    student__is_active=True,
                    student__deleted_at__isnull=True,
                    has_custody=True,
                    is_active=True,
                ).exists():
                    return None, "access_revoked"
            if not user or not user.is_active:
                return None, (
                    "access_revoked" if user and user.email_verified_at else "account_not_activated"
                )
            if not AnnouncementAudienceSelector.is_eligible(receipt, user):
                return None, "access_revoked"
        elif delivery.source_type in {
            "activity",
            "calendar_event",
            "enrollment_application",
            "payment",
        }:
            from notifications.domain_event_selectors import DomainEventAudience

            if not DomainEventAudience.eligible(delivery, user):
                return None, "access_revoked"
        elif delivery.source_type in {"enrollment_reminder", "financial_reminder"}:
            from notifications.reminder_selectors import ReminderDeliverySelector

            if not ReminderDeliverySelector.eligible(delivery, user):
                return None, "access_revoked"
        elif delivery.source_type == "service_requests":
            from service_requests.delivery_selectors import RequestDeliverySelector

            if not user or not RequestDeliverySelector.eligible(delivery, user):
                return None, "access_revoked"
        elif delivery.source_type == "student_diary":
            if not user or not user.is_active or user.deleted_at:
                return None, "access_revoked"
            if delivery.payload["event"] == "publication":
                from student_diary.selectors import StudentDiarySelector

                try:
                    StudentDiarySelector().get_published_entry_for_guardian(
                        delivery.source_id, user.pk
                    )
                except (ObjectNotFoundError, PermissionDeniedError):
                    return None, "access_revoked"
            else:
                from core.access_selectors import ObjectAccessSelector
                from core.permissions import can_access, role_name
                from student_diary.contracts import DiarySheet

                sheet = DiarySheet.objects.filter(pk=delivery.source_id).first()
                if not sheet:
                    return None, "access_revoked"
                if delivery.payload["event"] == "review_requested":
                    if role_name(user) not in {"ADMIN", "COORDINATOR"} or not can_access(
                        user, "student_diary", "edit"
                    ):
                        return None, "access_revoked"
                elif not (
                    can_access(user, "student_diary", "view")
                    and (
                        role_name(user) in {"ADMIN", "COORDINATOR"}
                        or ObjectAccessSelector.teacher_can_access_class(
                            user.pk, sheet.class_obj_id
                        )
                    )
                ):
                    return None, "access_revoked"
        else:
            return None, "unsupported_source"
        return user, ""
