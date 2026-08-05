"""
Request-scoped context variables (async-safe via contextvars).

Definidos aqui (base/) para evitar dependência circular:
  core → base  ✓
  base → core  ✗ (evitado)

Os middlewares em core/middleware.py importam daqui e definem os valores.
Services e AuditService lêem daqui.
"""

import contextlib
import uuid
from collections.abc import Iterator
from contextvars import ContextVar

# ID único por requisição — propagado em logs, respostas e auditoria
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

# Schema do tenant ativo (definido pelo TenantMainMiddleware)
current_tenant: ContextVar[str] = ContextVar("current_tenant", default="public")

# PK do usuário autenticado (definido pelo AuditContextMiddleware)
user_id: ContextVar[int | None] = ContextVar("user_id", default=None)

# IP do cliente
request_ip: ContextVar[str] = ContextVar("request_ip", default="")

# User-Agent da requisição
user_agent: ContextVar[str] = ContextVar("user_agent", default="")


def generate_correlation_id() -> str:
    """Gera um novo correlation ID RFC 4122 v4."""
    return str(uuid.uuid4())


def active_tenant_schema() -> str:
    """Retorna o schema escolar ativo, recusando contexto ausente ou público."""
    from base.exceptions import BusinessRuleViolationError

    schema_name = str(current_tenant.get() or "").strip()
    if not schema_name or schema_name == "public":
        raise BusinessRuleViolationError("O schema da escola é obrigatório.")
    return schema_name


def require_tenant_schema(expected: str) -> str:
    """Confirma que o schema explícito corresponde ao contexto escolar ativo."""
    from base.exceptions import BusinessRuleViolationError

    expected_schema = str(expected or "").strip()
    if not expected_schema or expected_schema == "public":
        raise BusinessRuleViolationError("O schema da escola é obrigatório.")
    active_schema = active_tenant_schema()
    if expected_schema != active_schema:
        raise BusinessRuleViolationError("O schema informado não corresponde à escola ativa.")
    return active_schema


@contextlib.contextmanager
def tenant_schema_context(schema_name: str) -> Iterator[None]:
    """Ativa um schema real ou funciona como no-op no perfil SQLite de testes."""
    from django.conf import settings

    token = current_tenant.set(schema_name)
    try:
        if getattr(settings, "TESTING", False):
            yield
            return

        from django_tenants.utils import schema_context

        with schema_context(schema_name):
            yield
    finally:
        current_tenant.reset(token)
