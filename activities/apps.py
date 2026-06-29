"""Configuração do app de atividades."""

from django.apps import AppConfig


class ActivitiesConfig(AppConfig):
    """Configura o app Django `activities` (avaliações)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "activities"
    verbose_name = "Atividades"
