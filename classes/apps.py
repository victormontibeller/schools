"""Configuração do app de turmas e matrículas."""

from django.apps import AppConfig


class ClassesConfig(AppConfig):
    """Configura o app Django `classes` (turmas)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "classes"
    verbose_name = "Turmas"
