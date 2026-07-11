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

## Observabilidade

- [ ] Logs implementados em toda operação de escrita (`self._log()`)
- [ ] Auditoria implementada (`self._record_audit()`)
- [ ] Exceções usam `base/exceptions.py`

## Testes

- [ ] Testes escritos (`test_<verbo>_<condição>()`)
- [ ] `pytest` verde (nenhum teste quebrado)
- [ ] Cobertura do módulo ≥ 80%

## Documentação

- [ ] Docstrings em módulos, classes e funções públicas
- [ ] Documentação atualizada se decisão arquitetural
- [ ] ADR criado em `docs/adr/` se nova decisão significativa
