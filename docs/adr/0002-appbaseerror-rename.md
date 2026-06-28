# ADR-0002 — Renomeio `AppBaseException` → `AppBaseError`

**Status:** Aceito
**Data:** 2026-06-28

## Contexto

A regra `N818` do Ruff exige que classes-filha de `Exception` terminem com
`Error` por convençãoPEP 8 / comunidadepython. A hierarquia original era:
`AppBaseException` → `TenantNotFoundError`, `PermissionDeniedError`,
`ValidationError`, `ObjectNotFoundError`, `BusinessRuleViolationError`.
Apenas a raiz divergia; as filhas já seguiam a convenção.

## Decisão

Renomear a raiz para `AppBaseError`. Nenhuma outra classe foi tocada.

## Consequências

- Hierarquia 100% conforme PEP 8.
- Imports em clientes não mudaram — exceto quem importava explicitamente
  `AppBaseException` (verificado: nenhum, era referenciada apenas em
  `base/exceptions.py`).
- Lint Ruff passa sem exceções necessárias para essa regra.

## Alternativas consideradas

- Ignorar `N818` globalmente — rejeitada: a regra capta valor em filhas; pylint
  recomenda a convenção; o custo do renomeio foi mínimo.