"""AuditService: registra entradas de auditoria para mutações de domínio."""

import logging

from audit.models import AuditLog
from base import context
from base.services import BaseService

logger = logging.getLogger(__name__)

SENSITIVE_FIELD_FRAGMENTS: frozenset[str] = frozenset(
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
        "address",
        "avatar",
        "document",
    }
)
SENSITIVE_EXACT_FIELDS: frozenset[str] = frozenset(
    {
        "recipient",
        "street",
        "number",
        "complement",
        "district",
        "postal_code",
        "city",
        "state",
        "birth_date",
    }
)
SENSITIVE_TEXT_TOKENS: frozenset[str] = frozenset(
    {
        "reason",
        "justification",
        "note",
        "notes",
        "observation",
        "observations",
        "rg",
        "file",
        "feedback",
        "message",
        "body",
        "content",
        "description",
        "title",
    }
)


def is_sensitive_audit_field(field_name: str) -> bool:
    """Identifica campos cujo conteúdo futuro deve ser redigido da auditoria."""
    normalized = field_name.strip().lower()
    if normalized == "id" or normalized.endswith("_id"):
        return False
    if normalized in SENSITIVE_EXACT_FIELDS:
        return True
    if any(fragment in normalized for fragment in SENSITIVE_FIELD_FRAGMENTS):
        return True
    return bool(set(normalized.split("_")) & SENSITIVE_TEXT_TOKENS)


def redact_nested_audit_value(value):
    """Redige recursivamente conteúdo sensível em estruturas serializáveis."""
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if is_sensitive_audit_field(str(key))
                else redact_nested_audit_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_nested_audit_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_nested_audit_value(item) for item in value)
    return value


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
            if is_sensitive_audit_field(name):
                data[name] = "[REDACTED]"
                continue
            value = getattr(instance, name, None)
            if isinstance(value, dict | list | tuple):
                value = redact_nested_audit_value(value)
            elif hasattr(value, "isoformat"):
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
        return redact_nested_audit_value(values)
