from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"

    def ready(self) -> None:
        """Registra adaptadores, handlers e seeds idempotentes."""
        from core.adapters import register_base_adapters

        register_base_adapters()
        from core import signals  # noqa: F401
