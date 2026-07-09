"""Fixtures compartilhadas para toda a suíte de testes."""

import asyncio
import inspect

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
    for slot in getattr(cls, "__slots__", ()) or ():
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

# Django 5.1 ainda usa `asyncio.iscoroutinefunction` em decorators de auth.
# Em Python novo, essa API emite DeprecationWarning; o alias mantém o
# comportamento esperado nos testes ate o upgrade do Django.
asyncio.iscoroutinefunction = inspect.iscoroutinefunction


@pytest.fixture()
def user(db):
    from core.models import CustomUser

    return CustomUser.objects.create_user(
        email="admin@test.com",
        password="Senha123",
        first_name="Admin",
        last_name="Test",
    )


def with_tenant(tenant):
    """Ativa o contexto de tenant (schema) para o bloco `with`.

    Uso::

        with with_tenant(school):
            # queries dentro deste bloco rodam no schema do `school`

    Em ambiente de testes SQLite (sem django_tenants) vira no-op seguro.

    Ver `docs/06_MULTI_TENANT.md` §57 "Helper with_tenant".
    """
    import contextlib

    from base import context

    @contextlib.contextmanager
    def _ctx():
        if not _django_tenants_enabled():
            yield
            return
        from django_tenants.utils import schema_context

        schema = tenant.schema_name if hasattr(tenant, "schema_name") else str(tenant)
        with schema_context(schema):
            token = context.current_tenant.set(schema)
            try:
                yield
            finally:
                context.current_tenant.reset(token)

    return _ctx()


# Exposição no pytest namespace para uso direto em testes de integração tenant.
@pytest.fixture()
def tenant_ctx(db):
    """Helper equivalente a `with_tenant(public)` — ativa schema público.

    Para testes multi-schema (perfil `test_pg`), crie um Tenant e use
    `with_tenant(my_school)` dentro do teste.
    """
    if _django_tenants_enabled():
        with with_tenant("public"):
            yield
    else:
        yield


def _django_tenants_enabled() -> bool:
    """Detecta se a run corrente tem django_tenants ativo (perfil full)."""
    try:
        from django.conf import settings

        return "django_tenants.middleware.main.TenantMainMiddleware" in settings.MIDDLEWARE
    except Exception:  # noqa: BLE001
        return False


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
