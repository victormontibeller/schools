"""Helpers de roteamento HTTP conforme o schema resolvido."""

from __future__ import annotations


def is_platform_request(request) -> bool:
    """Indica se a requisição pertence ao schema público da plataforma."""
    tenant = getattr(request, "tenant", None)
    if tenant is not None:
        return getattr(tenant, "schema_name", "") == "public"

    # No perfil SQLite o TenantMainMiddleware não está ativo. O fallback por
    # host mantém os testes e o desenvolvimento local fiéis ao roteamento real.
    hostname = request.get_host().partition(":")[0].lower()
    return hostname == "platform.localhost"
