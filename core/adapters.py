"""Adaptadores de infraestrutura registrados nas portas do pacote base."""


class AuditAdapter:
    """Conecta a porta genérica ao domínio de auditoria."""

    def record(self, *, user, operation, instance, old_values, new_values) -> None:
        from audit.services import AuditService

        AuditService(user=user).record(
            operation=operation,
            instance=instance,
            old_values=old_values,
            new_values=new_values,
        )


class AuthorizationAdapter:
    """Conecta a porta genérica à política RBAC do core."""

    def can_execute(
        self,
        user,
        app_label: str,
        method_name: str,
        service_name: str = "",
    ) -> bool:
        from core.permissions import can_execute_service

        return can_execute_service(user, app_label, method_name, service_name)


def register_base_adapters() -> None:
    """Registra os adaptadores concretos uma única vez no startup do Django."""
    from base.ports import register_audit_port, register_authorization_port

    register_audit_port(AuditAdapter())
    register_authorization_port(AuthorizationAdapter())
