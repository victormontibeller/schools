# Sprint 14 — UX e Produtividade

> **Documento histórico.** Em caso de divergência, prevalecem os documentos normativos em `docs/`.

## Objetivo

Melhorar a experiencia de uso da plataforma para secretaria, coordenacao e docentes, reduzindo cliques, tempo de resposta percebido e retrabalho em operacoes diarias.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [x] Fluxos de cadastro e edicao deverao ter menos friccao e validacao visual consistente.
- [x] Listagens principais deverao suportar busca, filtro e paginacao HTMX com estado preservado.
- [ ] Tempo medio de acao para tarefas administrativas comuns devera reduzir em pelo menos 30%.
- [x] Componentes de formulario deverao seguir padrao unico em todo o sistema.
- [x] Tela inicial devera apresentar atalhos operacionais por perfil.

---

## Tarefas

### Formularios e Layout

- [ ] Revisar templates de formulario para consistencia de labels, ajuda e erros.
- [x] Padronizar estados de carregamento e desabilitacao de botoes em submits.
- [x] Revisar componentes reutilizaveis em templates/partials.

### Listagens e Operacao

- [x] Implementar filtros salvos por usuario em modulos prioritarios.
- [x] Adicionar ordenacao de colunas nas tabelas principais.
- [ ] Incluir acoes em lote para operacoes repetitivas (ativar, desativar, exportar).

### Performance Percebida

- [ ] Aplicar lazy load em blocos secundarios.
- [x] Reduzir consultas redundantes em telas de maior uso.
- [ ] Ajustar polling HTMX para intervalos adequados por contexto.

### Acessibilidade Basica

- [ ] Revisar contraste, foco de teclado e navegacao por tab.
- [ ] Corrigir labels, aria e semantica em formularios criticos.

---

## Dependencias

- Sprints 03-08 concluidas
- Base de templates e partials consolidada

---

## Definition of Done

- [ ] Criterios de aceite validados
- [x] Testes de views e templates atualizados
- [ ] Fluxos alvo homologados com usuarios internos
- [ ] Regressao visual controlada nas telas alteradas

---

## Progresso Implementado

### Entregas desta iteracao

- Home interna reorganizada com atalhos operacionais por perfil e modulos em foco.
- Formularios base com estado de envio, desabilitacao de submit e feedback visual de salvamento.
- Listagens de alunos, responsaveis, professores e usuarios com:
  - busca HTMX com estado salvo por usuario em sessao;
  - ordenacao por colunas principais;
  - paginacao preservando contexto de busca e ordenacao;
  - cabecalho compartilhado padronizado.
- Campo de busca com acao de limpar embutida no proprio input.
- Selectors ajustados com `select_related` e `prefetch_related` nas listagens prioritarias para reduzir consultas redundantes.

### Validacao tecnica realizada

- `ruff check` verde nos arquivos alterados.
- `black --check` verde nos arquivos alterados.
- `manage.py check` sem issues.
- Testes de views cobrindo dashboard e listagens prioritarias atualizados e passando.
