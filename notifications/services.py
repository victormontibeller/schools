"""NotificationService e AnnouncementService: regras de negocio para notificacoes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.utils import timezone

from base import context
from base.exceptions import (
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.repositories import BaseRepository
from base.services import BaseService, system_command

if TYPE_CHECKING:
    from notifications.contracts import MessageTemplate, Notification

logger = logging.getLogger(__name__)


class _NotificationRepo(BaseRepository):
    @property
    def model_class(self):
        from notifications.contracts import Notification

        return Notification


class _TemplateRepo(BaseRepository):
    @property
    def model_class(self):
        from notifications.contracts import MessageTemplate

        return MessageTemplate


# ── NotificationService ────────────────────────────────────────────────────────


class NotificationService(BaseService):
    """Servico de aplicacao para notificacoes individuais in-app."""

    def _actor_id(self):
        """Retorna o destinatário autenticado sem aceitar escopo fornecido pelo cliente."""
        if self.user is None or not getattr(self.user, "is_authenticated", False):
            raise PermissionDeniedError("Ator autenticado obrigatório para esta operação.")
        return self.user.pk

    @system_command
    def create_notification(self, data: dict) -> Notification:
        """Cria uma notificacao para um usuario e registra auditoria.

        Args:
            data: dict com recipient_id, title, message, type? (INFO),
                  source?, action_url?, correlation_id?
        """
        from notifications.contracts import Notification

        self.validate_required(data, ["recipient_id", "title", "message"])

        from core.contracts import CustomUser

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
        """Marca como lida uma notificação do próprio destinatário, de forma idempotente."""
        from notifications.contracts import Notification

        try:
            notification = Notification.objects.select_for_update().get(
                pk=notification_id, recipient_id=self._actor_id()
            )
        except Notification.DoesNotExist:
            raise ObjectNotFoundError("Notification", str(notification_id)) from None

        if notification.read_at is not None:
            return notification
        old = self._snapshot(notification, ["read_at", "updated_by_id", "version"])
        notification.read_at = timezone.now()
        notification.updated_by = self.user
        notification.save(update_fields=["read_at", "updated_by"])
        self._record_audit("UPDATE", notification, old_values=old)
        self._log("notification_marked_as_read", notification_id=str(notification.pk))
        return notification

    def mark_all_as_read(self) -> int:
        """Marca todas as notificacoes nao lidas de um usuario como lidas.

        Returns:
            Quantidade de notificacoes marcadas como lidas.
        """
        from notifications.contracts import Notification

        actor_id = self._actor_id()
        notifications = list(
            Notification.objects.select_for_update().filter(
                recipient_id=actor_id, read_at__isnull=True
            )
        )
        if not notifications:
            return 0

        now = timezone.now()
        for notification in notifications:
            old = self._snapshot(notification, ["read_at", "updated_by_id", "version"])
            notification.read_at = now
            notification.updated_by = self.user
            notification.save(update_fields=["read_at", "updated_by"])
            self._record_audit("UPDATE", notification, old_values=old)

        count = len(notifications)
        self._log("notifications_marked_as_read", count=count)
        return count

    @system_command
    def create_notifications_bulk(self, recipient_ids: list, data: dict) -> int:
        """Cria notificacoes em lote mantendo autoria, auditoria e log estruturado."""
        from notifications.contracts import Notification

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
        from notifications.contracts import Notification

        return Notification.objects.filter(recipient_id=user_id, read_at__isnull=True).count()


class TemplateService(BaseService):
    """Configuração autorizada de modelos de mensagem."""

    def create_template(self, data: dict) -> MessageTemplate:
        """Cria um template de mensagem reutilizavel.

        Args:
            data: dict com name, channel, body, type? (CUSTOM),
                  subject?, variables?
        """
        from notifications.contracts import MessageTemplate

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
