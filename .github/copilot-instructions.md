# Copilot Instructions — School Manager

Plataforma SaaS Multi-Tenant de Gestão Escolar: Django 5.1, PostgreSQL (Schema por Tenant via django-tenants), HTMX, Alpine.js, Bootstrap, Celery + RabbitMQ, Redis.

## Arquitetura

Monólito Modular. Nunca proponha microserviços.

**Camadas obrigatórias** (em ordem):
`models.py` → `services.py` → `selectors.py` → `views.py` → `forms.py`

## Regras Invioláveis

- Regra de negócio **somente** em `services.py`. Nunca em views, forms, templates ou tasks.
- Consultas complexas **somente** em `selectors.py`. Nunca `Model.objects.filter()` em views.
- Toda entidade **deve** herdar de `BaseModel` (`base/models.py`).
- Todo service **deve** herdar de `BaseService` (`base/services.py`).
- Toda escrita **deve** chamar `self._record_audit("INSERT"|"UPDATE"|"DELETE", instance)`.
- `print()` é **proibido**. Usar `logging` com JSON estruturado via `self._log()`.
- PII (email, CPF, telefone, nome) **nunca** em logs — `BaseService._log()` bloqueia automaticamente.
- Soft delete obrigatório: nunca `instance.delete()`. Usar `instance.soft_delete(user=request.user)` ou `self._deactivate(Model, id, "Label")`.
- Segredos **nunca** em código. Usar variáveis de ambiente.
- Provedores externos (email, WhatsApp) via `notifications/channels/` SDK. Nunca chamar APIs diretamente em tasks.

## Exceções — Usar Sempre

```python
from base.exceptions import ValidationError, ObjectNotFoundError, BusinessRuleViolationError
raise ValidationError(errors={"field": ["Mensagem."]})
raise ObjectNotFoundError("ModelName", str(id))
raise BusinessRuleViolationError("Regra violada.")
```

## BaseService — Métodos DRY

```python
self.validate_required(data, ["field1", "field2"])       # valida obrigatórios
self._deactivate(ModelClass, entity_id, "Label")         # soft-delete + auditoria
self._log("event", key=value)                            # log sem PII
self._record_audit("INSERT"|"UPDATE"|"DELETE", instance) # auditoria
```

## Multi-Tenant (Celery)

Tasks Celery devem ativar o schema:
```python
from django_tenants.utils import schema_context

@shared_task
def my_task(tenant_schema: str, ...):
    with schema_context(tenant_schema):
        ...
```

## Testes

Framework: `pytest` + `pytest-django`. Cobertura mínima: 80%.
Fixtures: `conftest.py`. Use `@pytest.mark.django_db`.
Nomenclatura: `test_<verbo>_<condição>()`.

## Frontend (Templates Django)

Design System: **Duralux** (tema Bootstrap 5). Classes de layout com prefixo `nxl-*`.
- Toda tela herda de `base.html` ou `form_base.html`
- Formulários: `{% extends "form_base.html" %}` + campos via `{% include "partials/form_field.html" %}`
- Interatividade: **HTMX** (busca debounce, paginação, polling). Sem Alpine.js.
- Ícones: Feather Icons `<i class="feather-*">`
- Bootstrap via `{% static %}`, nunca CDN
- `{% csrf_token %}` obrigatório em todo `<form method="post">`

## Consultar Sempre

- `AGENTS.md` — guia completo com exemplos de código
- `docs/10_CODING_STANDARDS.md` — catálogo DRY de helpers
- `docs/03_ENGINEERING_RULES.md` — lista de proibições
- `docs/09_UI_GUIDELINES.md` — padrões de frontend
- `docs/adr/` — decisões arquiteturais registradas
