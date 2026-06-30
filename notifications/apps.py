from __future__ import annotations

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "Notificacoes"

    def ready(self) -> None:
        from notifications.handlers import register_event_handlers

        register_event_handlers()
