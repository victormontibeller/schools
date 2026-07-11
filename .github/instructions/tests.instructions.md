---
applyTo: "**/tests/**,**/tests.py"
---

# Testes — Padrões Obrigatórios

> Critérios de aceite estão em `docs/12_DEFINITION_OF_DONE.md`. Este arquivo cobre apenas convenções locais de testes.

Framework: `pytest` + `pytest-django`. Cobertura mínima: **80%**.

## Estrutura de um arquivo de teste

```python
"""Testes para MyService."""

import pytest
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def service(db_user):
    from my_app.services import MyService
    return MyService(user=db_user)


@pytest.fixture()
def my_model_factory(db_user):
    """Factory para criar instâncias de teste."""
    def _factory(**kwargs):
        from my_app.models import MyModel
        defaults = {"name": "Test", "created_by": db_user, "updated_by": db_user}
        defaults.update(kwargs)
        return MyModel.objects.create(**defaults)
    return _factory


# ── Testes de criação ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_create_succeeds_with_valid_data(service):
    result = service.create_entity({"field1": "value", "field2": "value2"})
    assert result.pk is not None
    assert result.field1 == "value"


@pytest.mark.django_db
def test_create_fails_when_required_field_missing(service):
    with pytest.raises(ValidationError) as exc_info:
        service.create_entity({"field1": "value"})  # field2 ausente
    assert "field2" in exc_info.value.errors


@pytest.mark.django_db
def test_create_fails_when_duplicate(service, my_model_factory):
    my_model_factory(field1="existing")
    with pytest.raises(ValidationError):
        service.create_entity({"field1": "existing", "field2": "x"})


# ── Testes de desativação ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_deactivate_succeeds(service, my_model_factory):
    instance = my_model_factory()
    service.deactivate_entity(instance.id)
    instance.refresh_from_db()
    assert instance.is_active is False
    assert instance.deleted_at is not None


@pytest.mark.django_db
def test_deactivate_fails_when_not_found(service):
    import uuid
    with pytest.raises(ObjectNotFoundError):
        service.deactivate_entity(uuid.uuid4())


@pytest.mark.django_db
def test_deactivate_fails_when_already_inactive(service, my_model_factory):
    instance = my_model_factory()
    service.deactivate_entity(instance.id)
    with pytest.raises(BusinessRuleViolationError):
        service.deactivate_entity(instance.id)
```

## Convenções

- Nomenclatura: `test_<verbo>_<condição>()`
  - `test_create_succeeds_with_valid_data`
  - `test_create_fails_when_required_field_missing`
  - `test_deactivate_fails_when_already_inactive`
- Sempre `@pytest.mark.django_db` para acesso ao banco
- Fixtures do projeto estão em `conftest.py` — `db_user`, etc.
- **Nunca** testar lógica de banco em testes unitários de service puro
- Cobrir: caminho feliz, validação de obrigatórios, unicidade, not found, regras de negócio

## Rodando os testes

```bash
pytest                          # todos os testes
pytest -x -q                    # parar no primeiro erro
pytest --cov=. --cov-report=term-missing  # com cobertura
pytest my_app/tests/            # módulo específico
```
