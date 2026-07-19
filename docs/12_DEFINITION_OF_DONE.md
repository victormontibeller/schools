# Definition of Done

> **Escopo:** checklist de entrega. Regras e padrões detalhados são definidos nos documentos de arquitetura, segurança, interface e código referenciados em `AGENTS.md`.

Um item **só pode ser considerado concluído** quando todos os critérios abaixo forem atendidos.

---

## Código

- [ ] Código funcional e revisado
- [ ] `ruff check .` — sem erros
- [ ] `black --check .` — sem erros
- [ ] Nenhum `print()` no código
- [ ] Nenhum secret em código (variáveis de ambiente)
- [ ] Nenhum PII em logs

## Banco de Dados

- [ ] Migration criada com `python manage.py makemigrations`
- [ ] Migration revisada (sem drops acidentais, índices adequados)
- [ ] Soft delete utilizado (nunca `instance.delete()`)

## Arquitetura

- [ ] Regras de negócio em `services.py`
- [ ] Consultas em `selectors.py`
- [ ] Views apenas com orquestração HTTP
- [ ] Toda entidade herda de `BaseModel`
- [ ] Nova tela ou mutação resolve módulo e ação do catálogo; chaves desconhecidas falham no CI
- [ ] Nova listagem usa `list_page_base.html` e consta em `LIST_PAGE_CATALOG`
- [ ] Nova grade primária usa `page_shell_base.html` e os utilitários canônicos de viewport,
      rolagem acessível, cabeçalho e primeira coluna fixos

## Observabilidade

- [ ] Logs implementados em toda operação de escrita (`self._log()`)
- [ ] Auditoria implementada (`self._record_audit()`)
- [ ] Exceções usam `base/exceptions.py`

## Testes

- [ ] Testes escritos (`test_<verbo>_<condição>()`)
- [ ] `pytest` verde (nenhum teste quebrado)
- [ ] Cobertura global ≥ 85%
- [ ] Cobertura ≥ 90% nos fluxos de contas, mídia privada, permissões, auditoria e financeiro
- [ ] Testes SQLite e PostgreSQL tenant-scoped verdes
- [ ] Concorrência cobre dois updates com a mesma versão: um sucesso e um conflito
- [ ] Permissões cobrem rota, botão, service, escopo de objeto, isolamento de tenant e ausência de override individual
- [ ] `python scripts/check_ui_contracts.py` verde
- [ ] Testes HTTP preservam a herança do shell e respostas HTMX contêm apenas o fragmento alvo
- [ ] `pytest -m ui --browser chromium` verde quando houver alteração de shell, listagem, grade ou CSS

## Supply chain e produção

- [ ] Dependências instaladas exclusivamente dos locks com hashes no Docker e no CI
- [ ] `check --deploy`, `makemigrations --check`, `pip-audit`, Gitleaks e Trivy verdes
- [ ] Imagens e Actions fixadas por digest/SHA imutável
- [ ] Migração de mídia, wildcard TLS e duas réplicas validadas em staging quando aplicável
- [ ] `collectstatic` gera manifesto e resolve o CSS customizado pelo nome com hash

## Documentação

- [ ] Docstrings em módulos, classes e funções públicas
- [ ] Documentação atualizada se decisão arquitetural
- [ ] ADR criado em `docs/adr/` se nova decisão significativa
