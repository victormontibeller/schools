"""
Request-scoped context variables (async-safe via contextvars).

Definidos aqui (base/) para evitar dependência circular:
  core → base  ✓
  base → core  ✗ (evitado)

Os middlewares em core/middleware.py importam daqui e definem os valores.
Services e AuditService lêem daqui.
"""

import uuid
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
