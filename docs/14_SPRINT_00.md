# Sprint 00 — Infraestrutura

## Objetivo

Configurar todo o ambiente de desenvolvimento e produção base, garantindo que todos os serviços necessários estejam disponíveis, funcional e integrados antes do início do desenvolvimento da aplicação.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [x] `docker compose up` deverá subir todos os serviços sem erros.
- [x] Django deverá estar acessível e respondendo `HTTP 200`.
- [x] PostgreSQL deverá estar acessível e com migrations aplicadas.
- [x] django-tenants deverá estar configurado com schema `public` e um tenant de teste.
- [x] Redis deverá estar acessível e funcional para cache e sessões.
- [x] RabbitMQ deverá estar acessível e com management UI disponível.
- [x] Celery worker deverá processar uma tarefa de teste com sucesso.
- [x] Celery beat deverá estar configurado e agendando tarefas.
- [ ] Traefik deverá estar roteando requisições corretamente.
- [ ] Grafana deverá exibir o dashboard com métricas do sistema.
- [ ] Prometheus deverá estar coletando métricas do Django.
- [ ] Loki deverá estar recebendo e indexando logs da aplicação.
- [x] `BaseModel` deverá estar implementado com todos os campos obrigatórios.
- [x] Logs deverão estar sendo emitidos em formato JSON estruturado.
- [x] Makefile deverá conter comandos para tarefas comuns de desenvolvimento.

---

## Tarefas

### Containerização

- [x] Criar `Dockerfile` para a aplicação Django (Python 3.13, multi-stage build)
- [x] Criar `docker-compose.yml` com todos os serviços:
  - `app` (Django + runserver dev / Gunicorn prod)
  - `worker` (Celery worker)
  - `beat` (Celery beat)
  - `db` (PostgreSQL)
  - `redis` (Redis)
  - `rabbitmq` (RabbitMQ + management plugin)
  - [ ] `traefik` (Proxy reverso)
  - [ ] `prometheus`
  - [ ] `grafana`
  - [ ] `loki`
- [x] Criar `.env.example` com todas as variáveis de ambiente necessárias
- [x] Criar `Makefile` com comandos: `setup`, `dev`, `test`, `lint`, `format`, `migrate`, `shell`, `worker`, `beat`, `up`, `down`, `logs`

### Django e Configurações

- [x] Criar projeto Django com estrutura modular em `src/`
- [x] Configurar `settings/` separados por ambiente (`base.py`, `development.py`, `production.py`, `testing.py`)
- [x] Configurar variáveis de ambiente via `python-decouple`
- [x] Configurar `ALLOWED_HOSTS`, `DEBUG`, `SECRET_KEY` via ambiente
- [x] Configurar Django para usar **Argon2** como hasher de senhas
- [x] Configurar `LANGUAGE_CODE = 'pt-br'` e `TIME_ZONE = 'America/Sao_Paulo'`

### Multi-Tenant

- [x] Instalar e configurar `django-tenants`
- [x] Criar model `School` (TenantMixin) e `Domain` (DomainMixin) no schema `public`
- [x] Configurar `DATABASE_ROUTERS` e `TENANT_MODEL`
- [x] Criar tenant `public` com domínio `localhost`
- [ ] Criar tenant de desenvolvimento `escola-teste` e validar isolamento de schemas

### BaseModel

- [x] Criar módulo `shared/` com `BaseModel`
- [x] Implementar campos: `id` (UUID), `created_at`, `updated_at`, `created_by`, `updated_by`, `deleted_at`, `version`
- [x] Implementar `ActiveManager` para filtrar `deleted_at__isnull=True` por padrão
- [x] Implementar método `soft_delete(user)` no `BaseModel`
- [x] Implementar método `restore(user)` no `BaseModel`

### Observabilidade

- [x] Configurar logging em JSON com `python-json-logger`
- [x] Implementar `CorrelationIdMiddleware` (gera UUID por requisição, injeta nos logs via `CorrelationIdFilter`)
- [ ] Configurar `django-prometheus` para expor métricas no endpoint `/metrics/`
- [ ] Configurar `promtail` ou SDK Loki para enviar logs ao Loki
- [ ] Criar dashboard inicial no Grafana com métricas básicas
- [ ] Configurar OpenTelemetry SDK no Django

### Segurança Inicial

- [x] Configurar CSRF, HSTS, XSS Protection e `X-Frame-Options` nas settings (`base.py` e `production.py`)
- [ ] Configurar HTTPS no Traefik (Let's Encrypt para produção, self-signed para dev)
- [ ] Instalar `django-ratelimit` e configurar rate limiting básico

### Health Check

- [x] Implementar endpoint `/health/` respondendo `{"status": "ok"}` com HTTP 200
- [ ] Expandir `/health/` para verificar conectividade: banco, Redis, RabbitMQ

---

## Dependências

Nenhuma. Esta Sprint é a base de todas as demais.

---

## Definition of Done

- [ ] `docker compose up` funciona sem erros
- [ ] Todos os critérios de aceite validados
- [x] `.env.example` documentado
- [ ] README com instruções de setup atualizado

---

## Progresso

> Atualizado em 2026-06-29

**Concluído nesta sprint:**
- Projeto Django criado em `src/` com settings por ambiente (`base`, `development`, `production`, `testing`)
- `django-tenants` configurado; tenant `public` + domínio `localhost` criados
- `BaseModel` com UUID PK, timestamps, soft-delete, restore, `ActiveManager` e versionamento
- Logging JSON estruturado com `python-json-logger` e filtro de `correlation_id`
- `.env.example` e `Makefile` completos
- Endpoint `/health/` respondendo `{"status": "ok"}` em `http://localhost:8000/health/`
- `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` (black + ruff + coverage), `pytest.ini`
- `Dockerfile` (Python 3.13-slim, Gunicorn, multi-stage)
- `docker-compose.yml` com PostgreSQL 15, Redis 7, RabbitMQ 3, Django app, Celery worker e beat
- CI (`ci.yml`) e `Makefile` atualizados com todas as 14 apps
- Cobertura de testes: 80.33% (284 testes), acima do limite de 80%

**Pendente:**
- Traefik, Prometheus, Grafana, Loki
- Rate limiting, HTTPS, tenant de teste isolado
- Health check expandido (banco, Redis, RabbitMQ)
