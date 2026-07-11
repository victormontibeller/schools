"""Configuração do app compartilhado de tenancy."""

from django.apps import AppConfig


class TenancyConfig(AppConfig):
    """Configura os modelos compartilhados entre todos os schemas."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tenancy"
    verbose_name = "Tenancy"
