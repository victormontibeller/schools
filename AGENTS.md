# AGENTS.md — Guia de contribuição assistida

> Este arquivo define regras invioláveis e a ordem de consulta. A documentação canônica fica em `docs/`.

## Antes de editar

1. Leia este arquivo inteiro.
2. Leia o documento canônico do domínio afetado.
3. Leia a instrução específica antes de editar `models.py`, `services.py`, `selectors.py`, `views.py`, `forms.py`, templates ou testes.
4. Reutilize helpers existentes antes de criar novos.

| Arquivo | Instrução local | Fonte canônica |
|---|---|---|
| `**/models.py` | `.github/instructions/models.instructions.md` | `docs/05_DATABASE.md` |
| `**/services.py` | `.github/instructions/services.instructions.md` | `docs/03_ENGINEERING_RULES.md` |
| `**/selectors.py` | `.github/instructions/selectors.instructions.md` | `docs/02_ARCHITECTURE.md` |
| `**/views.py` | `.github/instructions/views.instructions.md` | `docs/02_ARCHITECTURE.md` |
| `**/forms.py` | `.github/instructions/forms.instructions.md` | `docs/10_CODING_STANDARDS.md` |
| `**/templates/**/*.html` | `.github/instructions/templates.instructions.md` | `docs/09_UI_GUIDELINES.md` |
| `**/tests/**` ou `**/tests.py` | `.github/instructions/tests.instructions.md` | `docs/12_DEFINITION_OF_DONE.md` |

## Projeto

School Manager é um monólito modular Django 5.2, Python 3.13 e PostgreSQL com `django-tenants`. A arquitetura, os módulos e a infraestrutura estão em `docs/02_ARCHITECTURE.md`; regras de tenancy estão em `docs/06_MULTI_TENANT.md`.

## Regras invioláveis

- Regra de negócio somente em `services.py`; views apenas orquestram HTTP.
- Consultas complexas somente em `selectors.py`; SQL direto é proibido.
- Toda escrita usa `BaseService`, gera auditoria e log estruturado sem PII.
- Nunca registrar e-mail, CPF, telefone, nome, senha, endereço ou avatar em logs.
- Todo modelo de domínio herda de `BaseModel`; exclusão física é proibida.
- Usar apenas `ValidationError`, `ObjectNotFoundError`, `BusinessRuleViolationError` e
  `PermissionDeniedError` nos services; a última é exclusiva para negação de autorização ou
  escopo de objeto.
- Secrets ficam em variáveis de ambiente; provedores externos usam `notifications/channels/`.
- O schema do tenant é obrigatório em requests e tarefas Celery.
- Não usar `print()` para logging.

## Helpers obrigatórios

Não reimplementar métodos de `BaseService`:

- `validate_required()` para campos obrigatórios;
- `_deactivate()` para soft delete;
- `_record_audit()` para auditoria;
- `_log()` para log estruturado sem PII.

## Frontend

`docs/09_UI_GUIDELINES.md` é a única fonte de verdade para listagens, fichas, edição HTMX, formulários, avatar/logotipo e acessibilidade. Em particular:

- usar o cabeçalho e componentes compartilhados;
- primeira coluna da tabela é o link principal;
- não repetir Ver/Editar em coluna Ações;
- edição inline substitui somente o card;
- avatar/foto/logotipo são editáveis no topo, sem “Choose file” no corpo.

## Testes e conclusão

- Framework: `pytest` + `pytest-django`; testes seguem `test_<verbo>_<condição>`.
- Cobrir services, regras de negócio, erros, auditoria e isolamento de tenant quando aplicável.
- Definition of Done completa: `docs/12_DEFINITION_OF_DONE.md`.
- Uma alteração só está pronta com `ruff check .`, `black --check .`, testes relevantes e documentação/ADR atualizados quando necessário.

## Subagentes

- Em tarefas grandes, delegar automaticamente quando houver pelo menos duas frentes independentes, investigação ampla ou mudança atravessando múltiplas camadas.
- Usar `school_explorer` para mapear o código, `school_builder` para implementar, `school_guardian` para segurança e testes e `school_reviewer` para a revisão final.
- Não delegar correções pequenas e localizadas quando a coordenação custar mais do que a execução direta.
- Entre os subagentes, somente `school_builder` pode editar. Enquanto ele estiver escrevendo, o agente principal aguarda; a integração começa após sua conclusão.
- O agente principal mantém requisitos, decisões, integração e validação final, espera os agentes solicitados e consolida os resultados.
- Manter a profundidade padrão de um nível; subagentes não delegam para outros subagentes.

## Mapa documental

| Assunto | Documento oficial |
|---|---|
| Visão e produto | `docs/00_PROJECT_VISION.md`, `docs/01_PRD.md` |
| Arquitetura e camadas | `docs/02_ARCHITECTURE.md`, `docs/03_ENGINEERING_RULES.md` |
| Segurança | `docs/04_SECURITY.md` |
| Dados e tenancy | `docs/05_DATABASE.md`, `docs/06_MULTI_TENANT.md` |
| Observabilidade e API | `docs/07_OBSERVABILITY.md`, `docs/08_API_STANDARDS.md` |
| Interface | `docs/09_UI_GUIDELINES.md` |
| Código e entrega | `docs/10_CODING_STANDARDS.md`, `docs/12_DEFINITION_OF_DONE.md` |
| Decisões | `docs/adr/` |
| Histórico | `docs/14_SPRINT_00.md` a `docs/35_SPRINT_21.md` |
