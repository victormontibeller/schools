# ADR-0004 — Ampliação do `BaseModel` com `is_active` e `deleted_by`

**Status:** Aceito
**Data:** 2026-06-28

## Contexto

`docs/05_DATABASE.md` §16-27 lista como **obrigatórios** os seguintes campos
para todo modelo de domínio:

- `id`, `created_at`, `updated_at`, `created_by`, `updated_by`,
- `deleted_at`, **`deleted_by`**, **`is_active`**,
- `version` (controle otimista de concorrência).

A implementação prévia do `BaseModel` em `base/models.py` possuía tudo —
exceto `deleted_by` e `is_active`. A ausência era uma divergência doc↔código
e enfraquecia a semântica de soft-delete: não era possível saber **quem**
desativou um registro, nem suspender um registro sem apagá-lo.

## Decisão

Adicionar a `BaseModel`:

- `is_active = BooleanField(default=True, db_index=True)`
  (default True; soft-delete o tornará False sem afetar `deleted_at`).
- `deleted_by = ForeignKey(AUTH_USER_MODEL, null=True, on_delete=SET_NULL)`
  com `related_name="%(app_label)s_%(class)s_deleted"`.

`ActiveManager.get_queryset` passa a filtrar **ambos** defensivamente:
`is_active=True, deleted_at__isnull=True`.

`soft_delete(user)` agora preenche `is_active=False` e `deleted_by=user`.
`restore(user)` inverte: `is_active=True`, `deleted_by=None`.

## Caso especial: `CustomUser`

`CustomUser` herda de `AbstractBaseUser` (que já declara `is_active`) e de
`BaseModel`. declares `is_active` explicitamente em `core/models.py` antes da
herança de `BaseModel` override → sem colisão (Django permite que a subclasse
redeclare fields para resolver conflitos MRO).

## Consequências

- Toda query `.objects.*()` agora exige `is_active=True` (não basta
  `deleted_at__isnull`). Comportamento poderoso: suspender sem apagar
  (`is_active=False, deleted_at=None`).
- Migrações foram **recriadas do zero** (pré-MVP, aceito pelo mantenedor).
- Testes em `core/tests/test_base_model.py` cobrem os invariantes:
  - `soft_delete` seta ambos os campos.
  - `restore` limpa ambos.
  - `ActiveManager` exclui suspenso sem apagar.

## Alternativas consideradas

- **Manter só `deleted_at`, derivar `is_active` como `@property`** — impossível
  filtrar no ORM (queries `.filter(is_active=True)` não funcionam em properties).
- **Não adicionar `is_active` ao `BaseModel`,registra r ADR de exclusão
  justificada** — rejeitado pelo mantenedor: a doc é  explícita e o custo é
  mínimo.