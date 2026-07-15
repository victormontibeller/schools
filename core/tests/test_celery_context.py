"""Testes da propagação de contexto em mensagens Celery."""

from types import SimpleNamespace

from base import context
from core.celery_signals import (
    activate_operational_context,
    add_operational_context,
    reset_operational_context,
)


def test_publish_adds_correlation_id_and_tenant_headers():
    correlation_token = context.correlation_id.set("corr-123")
    tenant_token = context.current_tenant.set("colegio")
    try:
        headers = {}
        add_operational_context(headers=headers)
    finally:
        context.correlation_id.reset(correlation_token)
        context.current_tenant.reset(tenant_token)

    assert headers == {"correlation_id": "corr-123", "tenant_schema": "colegio"}


def test_worker_activates_and_resets_message_context():
    task = SimpleNamespace(
        request=SimpleNamespace(
            headers={"correlation_id": "worker-corr", "tenant_schema": "escola"}
        )
    )

    activate_operational_context(task=task)
    assert context.correlation_id.get() == "worker-corr"
    assert context.current_tenant.get() == "escola"

    reset_operational_context(task=task)
    assert context.correlation_id.get() == "test-corr-id"
    assert context.current_tenant.get() == "public"
