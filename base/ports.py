"""Portas registráveis para serviços de infraestrutura e autorização."""

from __future__ import annotations

from typing import Protocol


class AuditPort(Protocol):
    """Contrato do adaptador de auditoria."""

    def record(self, *, user, operation: str, instance, old_values, new_values) -> None: ...


class AuthorizationPort(Protocol):
    """Contrato do adaptador de autorização de comandos."""

    def can_execute(
        self,
        user,
        app_label: str,
        method_name: str,
        service_name: str = "",
    ) -> bool: ...


_audit_port: AuditPort | None = None
_authorization_port: AuthorizationPort | None = None


def register_audit_port(port: AuditPort) -> None:
    """Registra o adaptador de auditoria durante a inicialização do core."""
    global _audit_port
    _audit_port = port


def register_authorization_port(port: AuthorizationPort) -> None:
    """Registra o adaptador de autorização durante a inicialização do core."""
    global _authorization_port
    _authorization_port = port


def record_audit(*, user, operation: str, instance, old_values=None, new_values=None) -> None:
    """Delega a escrita de auditoria ao adaptador configurado."""
    if _audit_port is None:
        raise RuntimeError("Porta de auditoria não registrada.")
    _audit_port.record(
        user=user,
        operation=operation,
        instance=instance,
        old_values=old_values,
        new_values=new_values,
    )


def can_execute(
    user,
    app_label: str,
    method_name: str,
    service_name: str = "",
) -> bool:
    """Delega a política de autorização ao adaptador configurado."""
    if _authorization_port is None:
        raise RuntimeError("Porta de autorização não registrada.")
    return _authorization_port.can_execute(user, app_label, method_name, service_name)
