"""Fixtures compartilhadas para toda a suíte de testes."""

import pytest
from django.template.context import BaseContext

from base import context


# ── Workaround: Django 5.1.x + Python 3.14 ────────────────────────────────────
# `copy.copy(RequestContext)` em `store_rendered_templates` (test client)
# failha em Python 3.14 por causa de `super().__copy__()` em `BaseContext.__copy__`
# (`object` não define `__copy__` → `duplicate` vira super proxy sem `__dict__`).
# Substituímos `__copy__` por versão robusta que cria a instância corretamente.
# Quando Django lançar fix oficial, basta remover este patch.
def _patched_bctx_copy(self):
    cls = type(self)
    new = object.__new__(cls)
    # Copia slots se houver
    for slot in (getattr(cls, "__slots__", ()) or ()):
        if hasattr(self, slot):
            try:
                setattr(new, slot, getattr(self, slot))
            except AttributeError:
                pass
    # Copia atributos de instância via vars() (se houver __dict__)
    try:
        for k, v in vars(self).items():
            try:
                setattr(new, k, v)
            except AttributeError:
                pass
    except TypeError:
        pass  # slots-only
    return new


BaseContext.__copy__ = _patched_bctx_copy


@pytest.fixture()
def user(db):
    from core.models import CustomUser
    return CustomUser.objects.create_user(
        email="admin@test.com",
        password="Senha123",
        first_name="Admin",
        last_name="Test",
    )


@pytest.fixture(autouse=True)
def reset_context_vars():
    """Garante que context vars sejam resetados entre testes."""
    tokens = {
        "correlation_id": context.correlation_id.set("test-corr-id"),
        "current_tenant": context.current_tenant.set("public"),
        "user_id": context.user_id.set(None),
        "request_ip": context.request_ip.set(None),
        "user_agent": context.user_agent.set(""),
    }
    yield
    for var_name, token in tokens.items():
        getattr(context, var_name).reset(token)
