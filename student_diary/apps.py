"""Configuração do app de agenda infantil."""

from django.apps import AppConfig


class StudentDiaryConfig(AppConfig):
    """Configura o domínio tenant-scoped da agenda infantil."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "student_diary"
    verbose_name = "Agenda"
