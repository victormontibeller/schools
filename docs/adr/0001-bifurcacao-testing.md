# ADR-0001 — Bifurcação TESTING na `core/settings.py`

**Status:** Aceito (pré-existente, documentado retroativamente em 2026-06-28)
**Data:** 2026-06-28

## Contexto

O projeto adota isolamento multi-tenant **por Schema PostgreSQL** via
`django-tenants` (`docs/06_MULTI_TENANT.md`). Em ambientes de teste rápidos,
porém, subir PostgreSQL + um schema por tenant produz uma penalidade de segundos
por teste — inviável para uma suíte executada a cada salvamento de arquivo.
Por outro lado, **não exercitar o isolamento por schema em hipótese alguma** é
inaceitável para um SaaS: seria o ponto onde mais cabem bugs catastróficos de
segurança (vazamento de dados entre escolas).

## Decisão

Mantemos **dois perfis de teste** controlados pela constante `TESTING`
(detectada automaticamente pela presença de `pytest` em `sys.modules`):

1. **Perfil rápido (padrão, SQLite `:memory:`)** — `core.settings.TESTING=True`.
   Pula `django_tenants`, usa SQLite e fixtures mínimas. Cobertura das regras de
   negócio de cada service.

2. **Perfil multi-tenant completo (PostgreSQL real)** — opt-in via
   `DJANGO_ENV=test_pg`. A suíte usa PostgreSQL + `django_tenants` e valida
   isolamento por schema. Executada em PR e antes de release, mas não a cada
   salvamento de arquivo.

## Consequências

- Suíte inferior (<5s) roda continuamente durante o desenvolvimento.
- Pipeline de CI roda os **dois** perfis; o perfil PostgreSQL não pode ser
  opcional em PRs que tocam `core/models.py`, migrations, middleware de tenant
  ou services que manipulam dados por schema.
- Documentamos que testes que dependem de isolamento por schema NÃO podem ser
  marcados apenas com `@pytest.mark.django_db`; precisam também do marcador
  `@pytest.mark.tenant` (skip em SQLite).

## Riscos

- Perfil rápido pode dar falso verde quando há bug que só aparece por schema.
  Mitigado pelo perfil PostgreSQL obrigatório em PR.