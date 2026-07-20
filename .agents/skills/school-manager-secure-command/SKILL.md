---
name: school-manager-secure-command
description: Criar ou revisar comandos de escrita seguros nos services do School Manager, cobrindo autorização, transação, concorrência, auditoria, logs sem PII, soft delete, tenant e efeitos Celery após commit. Usar ao adicionar ou alterar métodos que criam, atualizam, vinculam, removem, aprovam, publicam, conciliam ou mudam estado persistido.
---

# Proteger comando de service

Tratar cada mutação como um comando autorizado, atômico, auditável e isolado por tenant.

## 1. Classificar o comando

- Usar o prefixo reconhecido pelo `BaseService` quando o nome expressar claramente a operação.
- Usar `@service_command` quando a mutação for iniciada por usuário e o nome não usar um prefixo reconhecido.
- Usar `@system_command` somente para comandos internos, infraestrutura ou webhooks autenticados fora da matriz de usuários.
- Não combinar esses decorators com `@transaction.atomic`; eles já fornecem atomicidade.
- Não usar `@system_command` para contornar uma permissão de produto.

## 2. Aplicar os invariantes

1. Resolver módulo e ação pelo catálogo de acesso; chaves desconhecidas devem negar.
2. Manter escrita e `_record_audit()` na mesma transação.
3. Emitir `_log()` sem nome, e-mail, CPF, telefone, endereço, avatar, token ou conteúdo sensível.
4. Usar `BaseRepository.update`, `BaseModel.save` ou versão esperada para concorrência otimista.
5. Usar `select_for_update()` para saldo, pagamento, sequência, vaga ou workflow com invariante agregada.
6. Usar `_deactivate()` ou `soft_delete()`; nunca excluir fisicamente um modelo de domínio.
7. Publicar Celery somente em `transaction.on_commit()` e passar o schema explicitamente.
8. Usar apenas as exceções de domínio permitidas pelo projeto.

## 3. Testar o comando

Cobrir conforme aplicável:

- sucesso e validações negativas;
- ator sem permissão, antes de qualquer escrita;
- not found e regra de negócio;
- auditoria e log sem PII;
- rollback da mutação quando a auditoria falhar;
- dois updates com a mesma versão;
- lock real no PostgreSQL para invariantes agregadas;
- ausência de tarefa Celery em rollback;
- isolamento entre tenants.

Executar ao final:

```bash
./.venv/bin/python scripts/check_service_contracts.py
./.venv/bin/pytest <app>/tests/ -q
./.venv/bin/ruff check .
./.venv/bin/black --check .
```

Executar a suíte tenant-scoped quando houver schema, lock ou constraint dependente do PostgreSQL.
