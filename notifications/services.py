"""NotificationService e AnnouncementService: regras de negocio para notificacoes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from base import context
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

if TYPE_CHECKING:
    from notifications.models import Announcement, MessageLog, MessageTemplate, Notification

logger = logging.getLogger(__name__)


class _NotificationRepo(BaseRepository):
    @property
    def model_class(self):
        from notifications.models import Notification

        return Notification


class _AnnouncementRepo(BaseRepository):
    @property
    def model_class(self):
        from notifications.models import Announcement

        return Announcement


class _TemplateRepo(BaseRepository):
    @property
    def model_class(self):
        from notifications.models import MessageTemplate

        return MessageTemplate


# ── NotificationService ────────────────────────────────────────────────────────


class NotificationService(BaseService):
    """Servico de aplicacao para notificacoes individuais in-app."""

    def create_notification(self, data: dict) -> Notification:
        """Cria uma notificacao para um usuario e registra auditoria.

        Args:
            data: dict com recipient_id, title, message, type? (INFO),
                  source?, action_url?, correlation_id?
        """
        from notifications.models import Notification

        self.validate_required(data, ["recipient_id", "title", "message"])

        from core.models import CustomUser

        try:
            recipient = CustomUser.objects.get(pk=data["recipient_id"])
        except CustomUser.DoesNotExist:
            raise ObjectNotFoundError("CustomUser", str(data["recipient_id"])) from None

        notification = Notification.objects.create(
            recipient=recipient,
            type=data.get("type", Notification.Type.INFO),
            title=data["title"].strip(),
            message=data["message"].strip(),
            source=data.get("source", ""),
            action_url=data.get("action_url", ""),
            correlation_id=data.get("correlation_id", context.correlation_id.get()),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", notification)
        self._log("Notificacao criada", notification_id=str(notification.pk))
        return notification

    def mark_as_read(self, notification_id) -> Notification:
        """Marca uma notificacao como lida.

        Raises:
            ObjectNotFoundError: se a notificacao nao existir.
            BusinessRuleViolationError: se ja estiver lida.
        """
        from notifications.models import Notification

        try:
            notification = Notification.objects.get(pk=notification_id)
        except Notification.DoesNotExist:
            raise ObjectNotFoundError("Notification", str(notification_id)) from None

        if notification.read_at is not None:
            raise BusinessRuleViolationError("Notificacao ja foi lida.")

        old = {"read_at": None}
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])
        self._record_audit("UPDATE", notification, old_values=old)
        return notification

    def mark_all_as_read(self, user_id) -> int:
        """Marca todas as notificacoes nao lidas de um usuario como lidas.

        Returns:
            Quantidade de notificacoes marcadas como lidas.
        """
        from notifications.models import Notification

        notifications = list(
            Notification.objects.filter(recipient_id=user_id, read_at__isnull=True)
        )
        if not notifications:
            return 0

        now = timezone.now()
        Notification.objects.filter(pk__in=[item.pk for item in notifications]).update(read_at=now)
        for notification in notifications:
            notification.read_at = now
            self._record_audit("UPDATE", notification, old_values={"read_at": None})

        count = len(notifications)
        self._log("Notificacoes marcadas como lidas", user_id=str(user_id), count=count)
        return count

    def create_notifications_bulk(self, recipient_ids: list, data: dict) -> int:
        """Cria notificacoes em lote mantendo autoria, auditoria e log estruturado."""
        from notifications.models import Notification

        self.validate_required(data, ["title", "message"])
        notifications = [
            Notification(
                recipient_id=recipient_id,
                type=data.get("type", Notification.Type.INFO),
                title=data["title"].strip(),
                message=data["message"].strip(),
                source=data.get("source", ""),
                action_url=data.get("action_url", ""),
                correlation_id=data.get("correlation_id", context.correlation_id.get()),
                created_by=self.user,
                updated_by=self.user,
            )
            for recipient_id in recipient_ids
        ]
        if not notifications:
            return 0

        Notification.objects.bulk_create(notifications, batch_size=500)
        for notification in notifications:
            self._record_audit("INSERT", notification)

        self._log("Notificacoes criadas em lote", count=len(notifications))
        return len(notifications)

    def get_unread_count(self, user_id) -> int:
        """Retorna o total de notificacoes nao lidas para o usuario."""
        from notifications.models import Notification

        return Notification.objects.filter(recipient_id=user_id, read_at__isnull=True).count()


# ── AnnouncementService ───────────────────────────────────────────────────────


class AnnouncementService(BaseService):
    """Servico de aplicacao para comunicados institucionais."""

    @transaction.atomic
    def create_announcement(self, data: dict) -> Announcement:
        """Cria um comunicado e opcionalmente agenda o envio.

        Args:
            data: dict com title, body, author_id, audience? (ALL),
                  class_obj_id?, send_email?, send_whatsapp?, scheduled_at?
        """
        from notifications.models import Announcement

        self.validate_required(data, ["title", "body", "author_id"])

        from core.models import CustomUser

        try:
            author = CustomUser.objects.get(pk=data["author_id"])
        except CustomUser.DoesNotExist:
            raise ObjectNotFoundError("CustomUser", str(data["author_id"])) from None

        audience = data.get("audience", Announcement.Audience.ALL)
        class_obj = None
        if audience == Announcement.Audience.CLASS:
            class_obj_id = data.get("class_obj_id")
            if not class_obj_id:
                raise ValidationError(
                    errors={"class_obj_id": ["Informe a turma para publico 'Turma especifica'."]}
                )
            from classes.models import Class

            try:
                class_obj = Class.objects.get(pk=class_obj_id)
            except Class.DoesNotExist:
                raise ObjectNotFoundError("Class", str(class_obj_id)) from None

        announcement = Announcement.objects.create(
            title=data["title"].strip(),
            body=data["body"].strip(),
            audience=audience,
            class_obj=class_obj,
            author=author,
            send_email=bool(data.get("send_email", False)),
            send_whatsapp=bool(data.get("send_whatsapp", False)),
            scheduled_at=data.get("scheduled_at"),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", announcement)
        self._log("Comunicado criado", announcement_id=str(announcement.pk))
        return announcement

    def send_announcement(self, announcement_id) -> Announcement:
        """Marca o comunicado como enviado e dispara tasks Celery por canal.

        Raises:
            ObjectNotFoundError: se o comunicado nao existir.
            BusinessRuleViolationError: se ja foi enviado.
        """
        from notifications.models import Announcement

        try:
            announcement = Announcement.objects.get(pk=announcement_id)
        except Announcement.DoesNotExist:
            raise ObjectNotFoundError("Announcement", str(announcement_id)) from None

        if announcement.sent_at is not None:
            raise BusinessRuleViolationError("Comunicado ja foi enviado.")

        now = timezone.now()
        old = {"sent_at": None}
        announcement.sent_at = now
        announcement.save(update_fields=["sent_at", "updated_at"])
        self._record_audit("UPDATE", announcement, old_values=old)

        # Dispara tasks Celery para cada canal habilitado.
        if announcement.send_email:
            from django.db import connection

            from notifications.tasks import send_announcement_email_task

            send_announcement_email_task.delay(connection.schema_name, str(announcement.pk))

        if announcement.send_whatsapp:
            from django.db import connection

            from notifications.tasks import send_announcement_whatsapp_task

            send_announcement_whatsapp_task.delay(connection.schema_name, str(announcement.pk))

        self._log("Comunicado enviado", announcement_id=str(announcement.pk))
        return announcement

    def get_audience_users(self, audience: str, class_id=None) -> QuerySet:
        """Retorna o queryset de usuarios de acordo com o publico-alvo.

        Args:
            audience: ALL, TEACHERS, STUDENTS, GUARDIANS, ou CLASS.
            class_id: PK da turma (obrigatorio para audience=CLASS).
        """
        from core.models import CustomUser

        audience_map = {
            "ALL": CustomUser.objects.filter(is_active=True),
            "TEACHERS": CustomUser.objects.filter(teacher_profile__isnull=False, is_active=True),
            "STUDENTS": CustomUser.objects.filter(student_profile__isnull=False, is_active=True),
            "GUARDIANS": CustomUser.objects.filter(guardian_profile__isnull=False, is_active=True),
        }
        if audience == "CLASS" and class_id:
            from classes.models import Enrollment

            student_user_ids = Enrollment.objects.filter(
                class_obj_id=class_id, status=Enrollment.Status.ACTIVE
            ).values_list("student__user_id", flat=True)
            return CustomUser.objects.filter(pk__in=student_user_ids, is_active=True)

        return audience_map.get(audience, CustomUser.objects.none())

    def create_template(self, data: dict) -> MessageTemplate:
        """Cria um template de mensagem reutilizavel.

        Args:
            data: dict com name, channel, body, type? (CUSTOM),
                  subject?, variables?
        """
        from notifications.models import MessageTemplate

        self.validate_required(data, ["name", "channel", "body"])

        name = data["name"].strip()
        channel = data["channel"]
        if MessageTemplate.objects.filter(name=name, channel=channel).exists():
            raise ValidationError(errors={"name": ["Ja existe template com este nome e canal."]})

        template = MessageTemplate.objects.create(
            name=name,
            channel=channel,
            type=data.get("type", MessageTemplate.Type.CUSTOM),
            subject=(data.get("subject") or "").strip(),
            body=data["body"].strip(),
            variables=data.get("variables", {}),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", template)
        self._log("Template criado", template_id=str(template.pk))
        return template

    def log_delivery(
        self,
        announcement=None,
        recipient=None,
        channel: str = "",
        recipient_address: str = "",
        status: str = "",
        error_message: str = "",
    ) -> MessageLog:
        """Registra uma tentativa de envio no log de entrega."""
        from notifications.models import MessageLog

        log_entry = MessageLog.objects.create(
            announcement=announcement,
            recipient=recipient,
            channel=channel,
            recipient_address=recipient_address,
            status=status or MessageLog.Status.PENDING,
            error_message=error_message,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", log_entry)
        self._log(
            "Entrega de mensagem registrada",
            message_log_id=str(log_entry.pk),
            channel=channel,
            status=log_entry.status,
        )
        return log_entry
