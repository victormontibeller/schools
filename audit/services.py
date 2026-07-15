"""AuditService: registra entradas de auditoria para mutações de domínio."""

import logging

from audit.models import AuditLog
from base import context
from base.services import BaseService

logger = logging.getLogger(__name__)

EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {
        "password",
        "token",
        "secret",
        "api_key",
        "email",
        "first_name",
        "last_name",
        "phone",
        "cpf",
        "rg",
        "address",
        "avatar",
        "file",
        "document",
    }
)


class AuditService(BaseService):
    """Serviço responsável por persistir entradas de auditoria de mutações."""

    def record_insert(self, instance) -> AuditLog:
        """Registra auditoria de inserção de uma instância de domínio."""
        return self._record(AuditLog.Operation.INSERT, instance, None, self._serialize(instance))

    def record_update(self, instance, old_values: dict) -> AuditLog:
        """Registra auditoria de atualização comparando valores antigos e novos."""
        return self._record(
            AuditLog.Operation.UPDATE, instance, old_values, self._serialize(instance)
        )

    def record_delete(self, instance) -> AuditLog:
        """Registra auditoria de exclusão lógica de uma instância."""
        return self._record(AuditLog.Operation.DELETE, instance, self._serialize(instance), None)

    def record_restore(self, instance) -> AuditLog:
        """Registra auditoria de restauração de uma instância excluída."""
        return self._record(AuditLog.Operation.RESTORE, instance, None, self._serialize(instance))

    def record(self, operation: str, instance, old_values=None, new_values=None) -> AuditLog:
        """Registra auditoria genérica com operação e valores informados."""
        return self._record(operation, instance, old_values, new_values)

    def _record(self, operation, instance, old_values, new_values) -> AuditLog:
        """Cria o `AuditLog` enriquecido com o contexto da requisição."""
        return AuditLog.objects.create(
            tenant_schema=context.current_tenant.get(),
            user=self.user,
            ip_address=context.request_ip.get() or None,
            user_agent=context.user_agent.get(),
            model_name=type(instance).__name__,
            object_id=str(instance.pk),
            operation=operation,
            old_values=self._redact(old_values),
            new_values=self._redact(new_values),
            correlation_id=context.correlation_id.get(),
        )

    @staticmethod
    def _serialize(instance) -> dict:
        """Serializa os campos do modelo, omitindo valores sensíveis."""
        data: dict = {}
        for field in instance._meta.get_fields():
            if not hasattr(field, "attname"):
                continue
            name: str = field.attname
            if any(ex in name.lower() for ex in EXCLUDED_FIELDS):
                data[name] = "[REDACTED]"
                continue
            value = getattr(instance, name, None)
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            elif not isinstance(value, int | float | bool | str | type(None)):
                value = str(value)
            data[name] = value
        return data

    @staticmethod
    def _redact(values: dict | None) -> dict | None:
        """Redige PII de snapshots fornecidos explicitamente pelo service."""
        if values is None:
            return None
        return {
            key: ("[REDACTED]" if any(ex in key.lower() for ex in EXCLUDED_FIELDS) else value)
            for key, value in values.items()
        }
