"""Testes de isolamento das chaves de cache por tenant."""

from base import context
from dashboard.services import DashboardService


def test_cache_key_changes_with_tenant_context():
    """Schemas diferentes nunca compartilham a mesma chave Redis."""
    token = context.current_tenant.set("escola_a")
    try:
        key_a = DashboardService._cache_key("total_students")
        token_b = context.current_tenant.set("escola_b")
        try:
            key_b = DashboardService._cache_key("total_students")
        finally:
            context.current_tenant.reset(token_b)
    finally:
        context.current_tenant.reset(token)
    assert key_a != key_b
    assert "escola_a" in key_a
    assert "escola_b" in key_b
