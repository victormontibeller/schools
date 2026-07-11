from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"
    verbose_name = "Auditoria"

    def ready(self) -> None:
        """Auditoria é síncrona no BaseService; não registra handler assíncrono."""
