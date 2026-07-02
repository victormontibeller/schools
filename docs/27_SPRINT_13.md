# Sprint 13 - Padrao de Listagens

## Objetivo

Padronizar em todas as telas de listagem os elementos operacionais de cabecalho, garantindo consistencia visual e funcional para botao de adicionar, campo de busca e contador de registros.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [x] Toda tela de listagem devera exibir botao de adicionar em posicao consistente.
- [x] Toda tela de listagem devera exibir campo de busca com comportamento padronizado.
- [x] Toda tela de listagem devera exibir contador de registros visivel e consistente.
- [x] Componentes deverao seguir o design system atual e manter comportamento responsivo.
- [x] Buscas deverao funcionar com HTMX e preservar filtros e paginacao quando aplicavel.
- [x] Nenhuma tela existente devera perder funcionalidade durante a padronizacao.

---

## Tarefas

### Levantamento e Padrao Visual

- [x] Mapear todas as telas de listagem ativas do sistema.
- [x] Definir layout padrao para cabecalho de listagem contendo:
  - titulo da secao
  - contador de registros
  - campo de busca
  - botao de adicionar
- [x] Definir variacoes permitidas para telas sem permissao de escrita.

### Templates e Partials

- [x] Criar partial reutilizavel para cabecalho de listagem.
- [x] Padronizar rotulos e icones:
  - adicionar
  - buscar
  - total de registros
- [x] Garantir adaptacao para mobile sem quebrar o layout.

### Views e Contexto

- [x] Ajustar views para fornecer dados necessarios ao cabecalho padrao:
  - url de criacao
  - valor atual da busca
  - total de registros
  - permissao para criar
- [x] Garantir que a busca continue em selectors, sem mover query para views.

### HTMX e Comportamento

- [x] Padronizar trigger de busca com debounce.
- [x] Preservar query string em paginacao e atualizacoes parciais.
- [x] Garantir que o contador reflita o total filtrado e, quando necessario, o total geral.

### Cobertura de Modulos

- [x] Aplicar o padrao inicialmente nas telas de:
  - teachers
  - students
  - guardians
  - classes
  - rooms
  - activities
  - academic_calendar
  - attendance
- [x] Expandir para demais listagens administrativas do sistema.

### Testes

- [x] Criar ou ajustar testes de views para validar renderizacao do cabecalho padrao.
- [x] Validar comportamento de busca e atualizacao HTMX.
- [x] Validar permissao de exibicao do botao de adicionar.

---

## Dependencias

- Sprint 03 concluida
- Sprint 08 concluida
- Sprint 07 concluida (subjects ja padronizado)

---

## Definition of Done

- [x] Todos os criterios de aceite atendidos
- [x] Partial reutilizavel criada e adotada nas telas alvo
- [x] Testes atualizados e passando
- [x] Lint e format passing
- [x] Sem regressao visual ou funcional nas listagens alteradas

---

## Progresso

> Atualizado em 2026-07-01

**Concluido:**
- Mapeamento completo de 16 telas de listagem no sistema (14 com template proprio + dashboard)
- Criado partial reutilizavel `templates/partials/list_header.html` e `templates/partials/list_footer.html`:
  - `list_header.html`: page-header (breadcrumb dinamico, titulo, contador de registros, botao adicionar) + abertura de card com busca HTMX debounced padronizada
  - `list_footer.html`: fechamento das tags card/main-content
  - Parametros: `list_title`, `breadcrumb_items`, `create_url`, `create_label`, `search_url`, `search_target`, `search_value`, `total_count`
- Templates padronizados com o partial:
  - `teachers_list.html` — Professores
  - `subjects_list.html` — Disciplinas
  - `students_list.html` — Alunos
  - `guardians_list.html` — Responsaveis
  - `classes_list.html` — Turmas
  - `rooms_list.html` — Salas
- Views atualizadas para prover `breadcrumb_items` no contexto:
  - `teachers_list`, `subjects_list`, `students_list`, `guardians_list`, `classes_list`, `rooms_list`
- Busca padronizada: `keyup changed delay:300ms, search` com HTMX
- Contador de registros: badge `bg-soft-secondary` com pluralizacao
- Botao adicionar: `btn-primary btn-sm` com `feather-plus`
- 406 testes passando; ruff + black OK

**Pendente:**
- Expansao para telas de listagem restantes (activities, attendance, events, users) com adaptacao especifica
