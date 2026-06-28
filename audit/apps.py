from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"
    verbose_name = "Auditoria"

    def ready(self) -> None:
        """Registra o handler que materializa DomainEvents em AuditLogs.

        Mantém o acoplamento entre `base` e o módulo de auditoria via
        evento-in-process (ver `docs/02_ARCHITECTURE.md` §136 e §182):
        BaseService dispara `DomainEvent`; o handler única chama AuditService.
        """
        from audit.services import AuditService
        from base.events import DomainEvent, dispatcher

        def _audit_handler(event: DomainEvent) -> None:
            AuditService(user=event.user).record(
                operation=event.operation,
                instance=event.instance,
                old_values=event.old_values,
                new_values=event.new_values,
            )

        dispatcher.register(DomainEvent, _audit_handler)
