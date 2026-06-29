"""Configuração do app de grade horária."""

from django.apps import AppConfig


class AgendaConfig(AppConfig):
    """Configura o app Django `agenda` (grade horária)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agenda"
    verbose_name = "Grade Horária"
