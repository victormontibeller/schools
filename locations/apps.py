"""Configuracao do app locations."""

from django.apps import AppConfig


class LocationsConfig(AppConfig):
    """Config do app de catalogos geograficos compartilhados."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "locations"
    verbose_name = "Localizacoes"
