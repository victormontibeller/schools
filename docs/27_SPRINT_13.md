# Sprint 13 - Padrao de Listagens

## Objetivo

Padronizar em todas as telas de listagem os elementos operacionais de cabecalho, garantindo consistencia visual e funcional para botao de adicionar, campo de busca e contador de registros.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [ ] Toda tela de listagem devera exibir botao de adicionar em posicao consistente.
- [ ] Toda tela de listagem devera exibir campo de busca com comportamento padronizado.
- [ ] Toda tela de listagem devera exibir contador de registros visivel e consistente.
- [ ] Componentes deverao seguir o design system atual e manter comportamento responsivo.
- [ ] Buscas deverao funcionar com HTMX e preservar filtros e paginacao quando aplicavel.
- [ ] Nenhuma tela existente devera perder funcionalidade durante a padronizacao.

---

## Tarefas

### Levantamento e Padrao Visual

- [ ] Mapear todas as telas de listagem ativas do sistema.
- [ ] Definir layout padrao para cabecalho de listagem contendo:
  - titulo da secao
  - contador de registros
  - campo de busca
  - botao de adicionar
- [ ] Definir variacoes permitidas para telas sem permissao de escrita.

### Templates e Partials

- [ ] Criar partial reutilizavel para cabecalho de listagem.
- [ ] Padronizar rotulos e icones:
  - adicionar
  - buscar
  - total de registros
- [ ] Garantir adaptacao para mobile sem quebrar o layout.

### Views e Contexto

- [ ] Ajustar views para fornecer dados necessarios ao cabecalho padrao:
  - url de criacao
  - valor atual da busca
  - total de registros
  - permissao para criar
- [ ] Garantir que a busca continue em selectors, sem mover query para views.

### HTMX e Comportamento

- [ ] Padronizar trigger de busca com debounce.
- [ ] Preservar query string em paginacao e atualizacoes parciais.
- [ ] Garantir que o contador reflita o total filtrado e, quando necessario, o total geral.

### Cobertura de Modulos

- [ ] Aplicar o padrao inicialmente nas telas de:
  - teachers
  - students
  - guardians
  - classes
  - rooms
  - activities
  - academic_calendar
  - attendance
- [ ] Expandir para demais listagens administrativas do sistema.

### Testes

- [ ] Criar ou ajustar testes de views para validar renderizacao do cabecalho padrao.
- [ ] Validar comportamento de busca e atualizacao HTMX.
- [ ] Validar permissao de exibicao do botao de adicionar.

---

## Dependencias

- Sprint 03 concluida
- Sprint 08 concluida
- Sprint 14 recomendada para consolidacao ampla de UX e produtividade

---

## Definition of Done

- [ ] Todos os criterios de aceite atendidos
- [ ] Partial reutilizavel criada e adotada nas telas alvo
- [ ] Testes atualizados e passando
- [ ] Lint e format passing
- [ ] Sem regressao visual ou funcional nas listagens alteradas