"""Configuração do app de frequência."""

from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    """Configura o app Django `attendance` (frequência)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "attendance"
    verbose_name = "Frequência"
