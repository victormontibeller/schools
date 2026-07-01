# Sprint 14 — UX e Produtividade

## Objetivo

Melhorar a experiencia de uso da plataforma para secretaria, coordenacao e docentes, reduzindo cliques, tempo de resposta percebido e retrabalho em operacoes diarias.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [ ] Fluxos de cadastro e edicao deverao ter menos friccao e validacao visual consistente.
- [ ] Listagens principais deverao suportar busca, filtro e paginacao HTMX com estado preservado.
- [ ] Tempo medio de acao para tarefas administrativas comuns devera reduzir em pelo menos 30%.
- [ ] Componentes de formulario deverao seguir padrao unico em todo o sistema.
- [ ] Tela inicial devera apresentar atalhos operacionais por perfil.

---

## Tarefas

### Formularios e Layout

- [ ] Revisar templates de formulario para consistencia de labels, ajuda e erros.
- [ ] Padronizar estados de carregamento e desabilitacao de botoes em submits.
- [ ] Revisar componentes reutilizaveis em templates/partials.

### Listagens e Operacao

- [ ] Implementar filtros salvos por usuario em modulos prioritarios.
- [ ] Adicionar ordenacao de colunas nas tabelas principais.
- [ ] Incluir acoes em lote para operacoes repetitivas (ativar, desativar, exportar).

### Performance Percebida

- [ ] Aplicar lazy load em blocos secundarios.
- [ ] Reduzir consultas redundantes em telas de maior uso.
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
- [ ] Testes de views e templates atualizados
- [ ] Fluxos alvo homologados com usuarios internos
- [ ] Regressao visual controlada nas telas alteradas
