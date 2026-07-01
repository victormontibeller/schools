# Sprint 07 - Frontend de Disciplinas

## Objetivo

Criar o frontend completo do modulo de disciplinas (`subjects`), incluindo listagem, busca, cadastro, edicao e exibicao consistente com o design system do projeto.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [ ] O sistema devera possuir tela de listagem de disciplinas.
- [ ] O sistema devera possuir tela de cadastro de disciplina.
- [ ] O sistema devera possuir tela de edicao de disciplina.
- [ ] A listagem devera suportar busca e contador de registros no padrao do sistema.
- [ ] O frontend devera respeitar o design system Duralux e os padroes de templates do projeto.
- [ ] O fluxo devera ser responsivo e funcional em desktop e mobile.
- [ ] O frontend nao devera quebrar o vinculo atual entre disciplinas e professores.

---

## Tarefas

### Listagem de Disciplinas

- [ ] Criar tela de listagem de disciplinas com:
  - titulo da pagina
  - botao de adicionar
  - campo de busca
  - contador de registros
  - tabela de resultados
- [ ] Incluir estado vazio com mensagem adequada.
- [ ] Integrar busca com HTMX e paginacao quando aplicavel.

### Cadastro e Edicao

- [ ] Criar tela de formulario para cadastro de disciplina.
- [ ] Criar tela de formulario para edicao de disciplina.
- [ ] Garantir uso de `form_base.html` e partials padrao de campo.
- [ ] Exibir mensagens de sucesso e erro no padrao do projeto.

### Campos da Disciplina

- [ ] Revisar os campos disponiveis em `Subject` e refleti-los corretamente no frontend.
- [ ] Garantir ao menos suporte visual para os campos atuais do modulo, como:
  - nome
  - codigo
  - carga horaria
- [ ] Preparar a tela para futuras extensoes sem refatoracao estrutural grande.

### Navegacao e UX

- [ ] Definir breadcrumbs e acoes consistentes entre listagem e formulario.
- [ ] Garantir fluxo claro de voltar, salvar e cancelar.
- [ ] Manter consistencia com os demais modulos administrativos.

### Views, Forms e Templates

- [ ] Ajustar ou criar views para renderizar listagem e formularios.
- [ ] Ajustar ou criar forms para suportar o frontend.
- [ ] Criar templates e partials necessarios para listagem e formulario.
- [ ] Garantir separacao correta entre view, form, selector e service.

### Testes

- [ ] Criar ou ajustar testes de views para listagem, cadastro e edicao.
- [ ] Criar testes de formulario para validacoes de campos.
- [ ] Validar renderizacao HTMX e comportamento da busca.

---

## Dependencias

- Sprint 03 concluida
- Sprint 13 recomendada para padronizacao do cabecalho das listagens
- Modulo `teachers` com model `Subject` ja existente

---

## Definition of Done

- [ ] Todos os criterios de aceite atendidos
- [ ] Templates de listagem e formulario implementados
- [ ] Testes atualizados e passando
- [ ] Lint e format passing
- [ ] Sem regressao nos fluxos atuais de professores e disciplinas