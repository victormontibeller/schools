"""Configuração do app de salas físicas."""

from django.apps import AppConfig


class RoomsConfig(AppConfig):
    """Configura o app Django `rooms` (salas físicas da escola)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "rooms"
    verbose_name = "Salas"
