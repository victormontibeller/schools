# ADR-0003 — Sistema de Eventos in-process Ligado à Auditoria

**Status:** Aceito
**Data:** 2026-06-28

## Contexto

`docs/02_ARCHITECTURE.md` §182–198 exige que toda ação importante produza um
evento interno, com auditação, notificações e dashboards cosumindo via handlers.
A implementação prévia chamava `AuditService.record(...)` diretamente de dentro
de `BaseService._record_audit`, sem qualquer evento. Isso:
- Acoplava `base.services` ao módulo `audit` (já mitigado por import lazy, mas
  ainda rígido).
- Impossibilitava adicionar notificações/dashboards sem refatorar todos os
  services.

## Decisão

Introduzir `DomainEvent` em `base/events.py` e fazer `BaseService._record_audit`
**despachar o evento** no `EventDispatcher` global, em vez de chamar o
`AuditService` diretamente. `audit` então se torna um **consumidor**:
`audit/apps.py:AuditConfig.ready()` registra um único handler que delega ao
`AuditService`.

Fluxo resultante:
```
Service → BaseService._record_audit → dispatcher.dispatch(DomainEvent)
                                                 ↓
                  [handler de auditoria registrado em AuditConfig.ready()]
                                                 ↓
                                          AuditService.record()
                                                 ↓
                                          AuditLog (persistência)
```

## Consequências

- Adicionar notificações (Sprint 11), dashboards (Sprint 12) ou um futuro
  outbox agora é só `dispatcher.register(DomainEvent, handler)` — zero mudanças
  em cada service.
- `base.services` não conhece mais `audit` — a regra de dependência
  (§136) fica puramente no sentido `audit → base`.
- Falhas em handlers NÃO derrubam services (`EventDispatcher.dispatch` envolve
  cada handler em `try/except` com log estruturado). Auditoria é um efeito
  colateral bestenável, nunca bloqueante.
- Isolamento de testes: o `dispatcher` é global; suítes que manipulam handlers
  devem monkeypatch (`tests/base/test_events.py`).
- Efeitos síncronos continuam no despacho e na transação corrente. Um handler que
  publica tarefa Celery deve registrar somente essa publicação com
  `transaction.on_commit()`, capturando schema, payload e Correlation ID. Assim,
  rollback não envia a tarefa e falha do broker após o commit não desfaz os dados.

## Riscos

- Ordem de execução de handlers não é determínística entre tipos diferentes —
  não há Garantia "auditoria antes de notificação". Aceito: handlers são
  independentes por design (idempotência esperada).
- Daemon/worker consumo futuro потенциальmente fora do processo: será tratado
  com outbox real (ADR separada em Sprint 11).
