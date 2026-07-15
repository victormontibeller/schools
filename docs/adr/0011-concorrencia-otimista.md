# ADR-0011 — Concorrência otimista e locks de invariantes

## Status

Aceito e implementado em 2026-07-13.

## Contexto

Uma coluna de versão sem update condicionado não evita lost updates. Em saldos, pagamentos,
sequências e vagas, a invariante também envolve mais de uma linha ou valor agregado.

## Decisão

- Formulários de edição enviam `version` oculta.
- Escritas usam `UPDATE ... WHERE id = ... AND version = expected`, incrementando a versão na
  mesma operação. Zero linhas afetadas produz conflito de negócio e reapresenta o card.
- `save`, soft delete, restore e transições incrementam versão e auditam na mesma transação.
- Pagamentos, cobranças, sequências e vagas usam `select_for_update` para invariantes agregadas.

## Consequências

Dois clientes com a mesma versão produzem um sucesso e um conflito, sem sobrescrita silenciosa.
Chamadores de edição devem transportar a versão lida; rotinas agregadas exigem PostgreSQL para
validar o comportamento real de locks.
