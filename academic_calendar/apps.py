"""Configuração do app de calendário acadêmico."""

from django.apps import AppConfig


class AcademicCalendarConfig(AppConfig):
    """Configura o app Django `academic_calendar` (calendário)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "academic_calendar"
    verbose_name = "Calendário"
