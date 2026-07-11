# Sprint 15 — Qualidade e Testes

> **Documento histórico.** Em caso de divergência, prevalecem os documentos normativos em `docs/`.

## Objetivo

Aumentar a confiabilidade da plataforma com foco em testes de regressao, cobertura por modulo, padronizacao de cenarios criticos e reducao de bugs em producao.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [ ] Cobertura total do projeto devera atingir pelo menos 85%.
- [ ] Cada app principal devera ter cobertura minima de 80%.
- [ ] Fluxos criticos deverao possuir testes de ponta a ponta com host de tenant.
- [ ] Falhas de regressao identificadas no backlog deverao estar cobertas por testes automatizados.
- [ ] Pipeline CI devera falhar automaticamente com cobertura abaixo do limite.

---

## Tarefas

### Testes de Servicos

- [ ] Revisar e ampliar testes de services nos apps:
  - accounts
  - students
  - attendance
  - classes
  - dashboard
- [ ] Adicionar cenarios negativos para validacoes de regra de negocio.
- [ ] Garantir asserts de auditoria em operacoes de escrita.

### Testes de Views e HTMX

- [ ] Cobrir views principais de listagem e formulario com foco em:
  - permissao e autenticacao
  - filtros e paginacao
  - respostas parciais HTMX
- [ ] Adicionar testes para mensagens de feedback (success e error).

### Testes Multi-Tenant

- [ ] Consolidar suite de isolamento por schema:
  - sem vazamento de dados entre tenants
  - validacao de dominio para resolucao de tenant
- [ ] Automatizar cenarios smoke para tenant demo.

### Qualidade de Pipeline

- [ ] Ajustar pyproject e/ou pytest para fail_under = 85.
- [ ] Publicar relatorio de cobertura por modulo no CI.
- [ ] Criar checklist de regressao para releases.

---

## Dependencias

- Sprints 00-10 concluidas
- Ambiente CI com execucao de testes em paralelo

---

## Definition of Done

- [ ] Criterios de aceite validados
- [ ] Cobertura global >= 85%
- [ ] Cobertura por app >= 80%
- [ ] CI verde com relatorio de cobertura anexado
- [ ] Sem regressao nos fluxos criticos priorizados
