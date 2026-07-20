---
name: school-manager-implement-feature
description: Implementar ou alterar funcionalidades do School Manager de ponta a ponta, respeitando o monólito modular Django, tenancy, services, selectors, views, HTMX, componentes canônicos e testes. Usar quando a tarefa pedir nova funcionalidade, novo fluxo, cadastro, listagem, ficha, formulário, regra de negócio ou mudança que atravesse mais de uma camada do projeto.
---

# Implementar funcionalidade no School Manager

Executar mudanças completas sem duplicar regras nem ignorar os contratos do repositório.

## 1. Delimitar a mudança

1. Ler `AGENTS.md` por inteiro.
2. Identificar o domínio afetado e ler a fonte canônica indicada no mapa documental.
3. Ler a instrução local de cada tipo de arquivo que será alterado.
4. Inspecionar fluxos equivalentes, helpers, contracts e componentes existentes antes de propor código novo.
5. Confirmar objetivo, critérios de aceite e limites que não possam ser descobertos no repositório.
6. Se a solicitação excluir produção, não ampliar o trabalho para deploy, hardening ou infraestrutura operacional.

## 2. Projetar pelas camadas

- Manter schema e persistência em `models.py`; usar `BaseModel` e soft delete.
- Colocar toda mutação e regra de negócio em services.
- Usar `$school-manager-secure-command` ao criar ou alterar qualquer mutação.
- Colocar consultas complexas, paginação e agregações em selectors.
- Limitar forms à validação de campo e views à orquestração HTTP.
- Usar `contracts.py`, selectors ou services públicos entre domínios; nunca importar models estrangeiros.
- Usar `$school-manager-build-ui` quando a funcionalidade criar ou alterar qualquer interface.
- Preservar contexto de tenant em requests, cache e tarefas Celery.

## 3. Implementar com segurança

1. Escrever ou ajustar testes junto da regra de negócio.
2. Implementar o menor conjunto coeso de mudanças.
3. Preservar compatibilidade de rotas e interfaces existentes, salvo decisão explícita em contrário.
4. Criar migration apenas quando o estado dos models mudar e revisá-la antes de aplicar.
5. Atualizar documentos canônicos quando o comportamento ou uma decisão arquitetural mudar.
6. Não reescrever documentos históricos de sprint.

## 4. Verificar conforme o risco

Executar sempre:

```bash
./.venv/bin/ruff check .
./.venv/bin/black --check .
./.venv/bin/python scripts/check_import_contracts.py
./.venv/bin/python scripts/check_service_contracts.py
./.venv/bin/python scripts/check_ui_contracts.py
./.venv/bin/python manage.py makemigrations --check --dry-run
```

Executar também:

- testes do domínio e fluxos HTTP afetados;
- suíte PostgreSQL tenant-scoped para schemas, constraints ou locks reais;
- suíte Chromium para shell, listagem, grade ou CSS;
- suíte completa quando a mudança atingir `base`, permissões, middleware ou contratos compartilhados.

Concluir somente após revisar o diff, preservar alterações alheias e relatar validações executadas e limitações restantes.
