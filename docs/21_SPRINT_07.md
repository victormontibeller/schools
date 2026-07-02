# Sprint 07 - Frontend de Disciplinas

## Objetivo

Criar o frontend completo do modulo de disciplinas (`subjects`), incluindo listagem, busca, cadastro, edicao e exibicao consistente com o design system do projeto.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [x] O sistema devera possuir tela de listagem de disciplinas.
- [x] O sistema devera possuir tela de cadastro de disciplina.
- [x] O sistema devera possuir tela de edicao de disciplina.
- [x] A listagem devera suportar busca e contador de registros no padrao do sistema.
- [x] O frontend devera respeitar o design system Duralux e os padroes de templates do projeto.
- [x] O fluxo devera ser responsivo e funcional em desktop e mobile.
- [x] O frontend nao devera quebrar o vinculo atual entre disciplinas e professores.

---

## Tarefas

### Listagem de Disciplinas

- [x] Criar tela de listagem de disciplinas com:
  - titulo da pagina
  - botao de adicionar
  - campo de busca
  - contador de registros
  - tabela de resultados
- [x] Incluir estado vazio com mensagem adequada.
- [x] Integrar busca com HTMX e paginacao quando aplicavel.

### Cadastro e Edicao

- [x] Criar tela de formulario para cadastro de disciplina.
- [x] Criar tela de formulario para edicao de disciplina.
- [x] Garantir uso de `form_base.html` e partials padrao de campo.
- [x] Exibir mensagens de sucesso e erro no padrao do projeto.

### Campos da Disciplina

- [x] Revisar os campos disponiveis em `Subject` e refleti-los corretamente no frontend.
- [x] Garantir ao menos suporte visual para os campos atuais do modulo, como:
  - nome
  - codigo
  - carga horaria
- [x] Preparar a tela para futuras extensoes sem refatoracao estrutural grande.

### Navegacao e UX

- [x] Definir breadcrumbs e acoes consistentes entre listagem e formulario.
- [x] Garantir fluxo claro de voltar, salvar e cancelar.
- [x] Manter consistencia com os demais modulos administrativos.

### Views, Forms e Templates

- [x] Ajustar ou criar views para renderizar listagem e formularios.
- [x] Ajustar ou criar forms para suportar o frontend.
- [x] Criar templates e partials necessarios para listagem e formulario.
- [x] Garantir separacao correta entre view, form, selector e service.

### Testes

- [ ] Criar ou ajustar testes de views para listagem, cadastro e edicao.
- [x] Criar testes de formulario para validacoes de campos.
- [ ] Validar renderizacao HTMX e comportamento da busca.

---

## Dependencias

- Sprint 03 concluida
- Sprint 13 recomendada para padronizacao do cabecalho das listagens
- Modulo `teachers` com model `Subject` ja existente

---

## Definition of Done

- [x] Todos os criterios de aceite atendidos
- [x] Templates de listagem e formulario implementados
- [x] Testes atualizados e passando
- [x] Lint e format passing
- [x] Sem regressao nos fluxos atuais de professores e disciplinas

---

## Progresso

> Atualizado em 2026-07-01

**Concluido:**
- `SubjectService` criado em `teachers/services.py`: `create_subject`, `update_subject`, `deactivate_subject` com validacao de codigo unico e auditoria
- Views em `teachers/views.py`: `subjects_list` (listagem HTMX com busca + paginacao), `subject_create`, `subject_edit`, `subject_deactivate`
- URLs em `teachers/urls.py`: `/subjects/`, `/subjects/novo/`, `/subjects/<pk>/editar/`, `/subjects/<pk>/desativar/`
- Templates:
  - `teachers/subjects_list.html` — listagem com breadcrumb, botao adicionar, contador de registros, busca HTMX com debounce
  - `teachers/subject_form.html` — form herdando `form_base.html` com cancel redirect
  - `teachers/partials/subjects_table.html` — tabela com colunas Nome/Codigo/Carga Horaria/Acoes, paginacao HTMX, confirmacao de desativacao, estado vazio
- Menu lateral `base.html`: link "Disciplinas" adicionado na secao "Academico"
- Dashboard: atalho "Disciplinas" adicionado aos modulos
- 406 testes passando; ruff + black OK

**Pendente:**
- Testes de views para fluxo de listagem, cadastro e edicao de disciplinas
