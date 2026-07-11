"""NotificationSelector: consultas otimizadas para o modulo de notificacoes."""

from __future__ import annotations

import logging

from django.db.models import Q

from base.selectors import MAX_PAGE_SIZE, BaseSelector, PageResult

logger = logging.getLogger(__name__)


class NotificationSelector(BaseSelector):
    """Selector de consultas para notificacoes individuais."""

    @property
    def model_class(self):
        from notifications.models import Notification

        return Notification

    def get_unread_for_user(self, user_id):
        """Notificacoes nao lidas ordenadas da mais recente."""
        return self.model_class.objects.filter(recipient_id=user_id, read_at__isnull=True).order_by(
            "-created_at"
        )

    def get_all_for_user(self, user_id):
        """Todas as notificacoes do usuario ordenadas da mais recente."""
        return self.model_class.objects.filter(recipient_id=user_id).order_by("-created_at")

    def get_by_type(self, user_id, notification_type: str):
        """Notificacoes do usuario filtradas por tipo."""
        return self.model_class.objects.filter(
            recipient_id=user_id, type=notification_type
        ).order_by("-created_at")

    def get_by_source(self, user_id, source: str):
        """Notificacoes do usuario filtradas por modulo de origem."""
        return self.model_class.objects.filter(recipient_id=user_id, source=source).order_by(
            "-created_at"
        )


class AnnouncementSelector(BaseSelector):
    """Selector de consultas para comunicados institucionais."""

    @property
    def model_class(self):
        from notifications.models import Announcement

        return Announcement

    def get_sent(self):
        """Retorna comunicados enviados, preservando o contrato de QuerySet."""
        return self.model_class.objects.filter(sent_at__isnull=False).order_by("-sent_at")

    def list_sent(self, search="", order_by="-sent_at", page=1, page_size=20) -> PageResult:
        """Lista comunicados enviados com busca, ordenação e paginação."""
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        page = max(1, page)
        queryset = self.get_sent().select_related("class_obj")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(body__icontains=search)
                | Q(audience__icontains=search)
            )
        total = queryset.count()
        offset = (page - 1) * page_size
        return PageResult(
            items=list(queryset.order_by(order_by)[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_scheduled(self):
        """Comunicados agendados ainda nao enviados."""
        return self.model_class.objects.filter(
            sent_at__isnull=True, scheduled_at__isnull=False
        ).order_by("scheduled_at")

    def get_by_audience(self, audience: str):
        """Comunicados filtrados por publico-alvo."""
        return self.model_class.objects.filter(audience=audience).order_by("-created_at")

    def get_for_class(self, class_id):
        """Comunicados de uma turma especifica."""
        return self.model_class.objects.filter(class_obj_id=class_id).order_by("-created_at")


class TemplateSelector(BaseSelector):
    """Selector de consultas para templates de mensagem."""

    @property
    def model_class(self):
        from notifications.models import MessageTemplate

        return MessageTemplate

    def get_by_channel(self, channel: str):
        """Templates filtrados por canal."""
        return self.model_class.objects.filter(channel=channel).order_by("name")

    def get_by_type(self, template_type: str):
        """Templates filtrados por tipo."""
        return self.model_class.objects.filter(type=template_type).order_by("name")
