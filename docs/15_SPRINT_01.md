# Sprint 01 — Arquitetura Base

## Objetivo

Estabelecer os padrões de código e as fundações arquiteturais que todos os módulos deverão seguir. Esta Sprint deverá criar as abstrações reutilizáveis que serão usadas em todas as sprints seguintes.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [x] `BaseService` deverá estar implementado com suporte automático a auditoria e logging.
- [x] `BaseRepository` deverá estar implementado com operações CRUD padronizadas.
- [x] `BaseSelector` deverá estar implementado para consultas somente-leitura.
- [x] Middleware de Tenant deverá identificar e ativar o schema correto em cada requisição.
- [x] Middleware de Correlation ID deverá injetar o ID em todos os logs da requisição.
- [x] Módulo de auditoria deverá registrar INSERT, UPDATE, DELETE e RESTORE.
- [x] Sistema de exceções customizadas deverá estar implementado.
- [x] Endpoint `/health/` deverá estar documentado e funcionando.
- [x] Pipeline de CI (lint + testes) deverá estar configurado.

---

## Tarefas

### Camadas Base — `base/`

- [x] Implementar `BaseService`:
  - Recebe `user` no construtor
  - Emite log estruturado via `_log()` com contexto de tenant e correlation ID
  - Chama auditoria automaticamente via `_record_audit()` (lazy import — sem dep. circular)

- [x] Implementar `BaseRepository`:
  - Métodos: `get_by_id`, `get_by_id_or_none`, `create`, `update`, `soft_delete`, `restore`, `list`
  - `update()` incrementa `version` automaticamente

- [x] Implementar `BaseSelector`:
  - Métodos: `get_by_id`, `list` com paginação via `PageResult`
  - `PageResult`: `items`, `total`, `page`, `page_size`, `total_pages`, `has_next`, `has_previous`

- [x] Implementar `BaseValidator`:
  - `add_error(field, message)` + `raise_if_errors()` com `ValidationError`

### Módulo `audit/`

- [x] Criar model `AuditLog` com campos:
  - `tenant_schema`, `user`, `ip_address`, `user_agent`
  - `model_name`, `object_id`
  - `operation` (INSERT, UPDATE, DELETE, RESTORE)
  - `old_values` (JSONField), `new_values` (JSONField)
  - `correlation_id`, `created_at`
- [x] Implementar `AuditService` com `record_insert`, `record_update`, `record_delete`, `record_restore`
  - `EXCLUDED_FIELDS = {"password", "token", "secret", "api_key"}` — campos sensíveis nunca persistidos
- [x] Registrar no Django Admin com filtros por data, usuário, modelo e operação (somente leitura)

### Middlewares — `core/middleware.py`

- [x] `TenantMainMiddleware` (via `django_tenants`): resolve tenant pelo domínio, ativa schema automaticamente
- [x] `CorrelationIdMiddleware`: gera UUID por requisição, armazena em `contextvars`, propaga no header `X-Correlation-ID`
- [x] `CorrelationIdFilter`: injeta `correlation_id` em cada log record
- [x] `AuditContextMiddleware`: captura IP (respeitando `X-Forwarded-For`) e User-Agent em `contextvars`

### Sistema de Exceções — `base/exceptions.py`

- [x] `AppBaseException` (raiz)
- [x] `TenantNotFoundError`
- [x] `PermissionDeniedError`
- [x] `ValidationError` (com dict de erros por campo)
- [x] `ObjectNotFoundError` (com `model_name` e `object_id`)
- [x] `BusinessRuleViolationError`
- [ ] Handler global de exceções para retornar respostas HTTP padronizadas

### Sistema de Eventos — `base/events.py`

- [x] `Event` (dataclass base com `correlation_id`)
- [x] `EventDispatcher`: `register(event_type, handler)`, `dispatch(event)`, `dispatch_type(type, **kwargs)`
- [x] Singleton global `dispatcher` importável em qualquer módulo
- [x] Erros em handlers são logados mas não interrompem a propagação

### Infraestrutura de Testes

- [x] Configurar `pytest` com `pytest-django` (settings: `core.settings`)
- [x] Settings único com detecção automática de TESTING via `"pytest" in sys.modules` (SQLite in-memory, sem `django_tenants`, sem dependências de `.env`)
- [x] Fixtures base em `conftest.py` na raiz: `user`, `reset_context_vars`
- [ ] `factories/` com `factory_boy` para modelos de domínio
- [ ] Helper `with_tenant(tenant)` para ativar contexto de tenant em testes

### CI/CD Básico

- [x] Configurar GitHub Actions (`.github/workflows/ci.yml`) com:
  - `ruff check base core accounts audit`
  - `black --check base core accounts audit`
  - `pytest --cov=. --cov-fail-under=80`
- [x] Jobs separados: `quality` (lint) e `test` (pytest), `test` depende de `quality`

---

## Dependências

- Sprint 00 concluída e validada

---

## Definition of Done

- [x] Todos os critérios de aceite validados
- [x] `BaseService`, `BaseRepository` e `BaseSelector` implementados
- [x] Módulo `audit/` com 7 testes passando (INSERT, UPDATE, DELETE, RESTORE, correlation_id, IP, campos sensíveis)
- [x] Pipeline CI configurado (`.github/workflows/ci.yml`)
- [x] `BaseService`, `BaseRepository` e `BaseSelector` com cobertura de testes completa
- [x] Estrutura achatada implementada: `base/` + `core/` sem `src/` ou `shared/` — 17/17 testes passando

---

## Progresso

> Atualizado em 2026-06-28

**Concluído:**
- `src/shared/` completo: `BaseModel`, `BaseService`, `BaseRepository`, `BaseSelector`, `BaseValidator`, `exceptions`, `events`, `middlewares`, `context`
- `src/audit/` completo: `AuditLog`, `AuditService`, admin read-only
- `src/config/` completo: `settings/` (base, development, production, testing), `urls.py`, `wsgi.py`, `asgi.py`, `celery.py`
- `src/schools/` stub criado para satisfazer `django_tenants` (será expandido no Sprint 02)
- Servidor rodando em `http://localhost:8000` via Play do VS Code
- 7/7 testes passando

**Pendente:**
- Handler global de exceções HTTP
- Factories com `factory_boy`
- Helper `with_tenant()` para testes
- Testes unitários de `BaseRepository` e `BaseSelector`
- ADR de decisões arquiteturais
