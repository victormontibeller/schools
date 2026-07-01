# Sprint 16 — Matricula e Secretaria

## Objetivo

Digitalizar o ciclo de secretaria escolar com foco em pre-matricula, matricula, rematricula, transferencia e controle documental.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [ ] Fluxo de pre-matricula devera permitir cadastro inicial e acompanhamento de status.
- [ ] Processo de matricula devera validar vagas por turma e periodo.
- [ ] Rematricula em lote devera estar disponivel por ano letivo.
- [ ] Transferencia interna e externa devera registrar historico completo.
- [ ] Pendencias documentais deverao ser rastreadas por aluno.

---

## Tarefas

### Processo de Matricula

- [ ] Criar estados de processo: pre_matricula, em_analise, aprovado, matriculado, recusado.
- [ ] Implementar service para consolidar regras de aceite e vagas.
- [ ] Criar selector para fila de analise por prioridade.

### Rematricula e Transferencia

- [ ] Criar fluxo anual de rematricula por turma.
- [ ] Implementar transferencia entre turmas com auditoria.
- [ ] Implementar transferencia de escola com encerramento controlado.

### Documentacao

- [ ] Registrar checklist documental por aluno.
- [ ] Notificar pendencias documentais por canal configurado.
- [ ] Adicionar filtros de pendencia no painel da secretaria.

### Interface de Secretaria

- [ ] Criar tela unica de operacao com tabs por etapa do processo.
- [ ] Adicionar atalhos para aprovar, rejeitar e solicitar correcoes.
- [ ] Suportar busca rapida por nome, numero de matricula e responsavel.

---

## Dependencias

- Sprints 03 e 04 concluidas
- Regras academicas basicas de turma e capacidade ativas

---

## Definition of Done

- [ ] Criterios de aceite validados
- [ ] Regras de matricula cobertas por testes de servico
- [ ] Fluxos de secretaria cobertos por testes de view
- [ ] Auditoria presente em toda escrita
