# Roadmap

## Visão Geral

O desenvolvimento deverá ser organizado em **Sprints de 2 semanas** cada.

Cada Sprint deverá entregar valor incrementável e funcional, com toda a infraestrutura de observabilidade e auditoria aplicada desde o início.

---

## Sprints

| Sprint | Nome | Objetivo Principal |
|---|---|---|
| **Sprint 00** | Infraestrutura | Ambiente completo: Docker, banco, cache, filas, observabilidade e Django base |
| **Sprint 01** | Arquitetura Base | Padrões de código: BaseModel, Services, Audit, Middleware, Logging |
| **Sprint 02** | Contas e Autenticação | Usuários, login, permissões, perfis, schools module |
| **Sprint 03** | Cadastros Principais | Professores, alunos e responsáveis |
| **Sprint 04** | Turmas e Agenda | Turmas, salas, grade horária e atividades |
| **Sprint 05** | Calendário | Calendário acadêmico, eventos e feriados |
| **Sprint 06** | Frequência | Controle de presença e relatórios de falta |
| **Sprint 07** | Comunicação | Notificações, e-mail e WhatsApp |
| **Sprint 08** | Dashboards | Dashboard técnico, escolar e executivo |
| **Sprint 09** | Produção | Docker Swarm, hardening, performance e monitoramento |
| **Sprint 10** | IA | Inteligência artificial para apoio pedagógico |

---

## Princípios do Roadmap

- Toda Sprint deverá incluir observabilidade e auditoria no escopo de cada entrega.
- Nenhuma Sprint poderá ser concluída sem passar pelo **Definition of Done**.
- O backlog poderá ser ajustado, mas a ordem das Sprints 00 e 01 é imutável.
- A Sprint 09 (Produção) deverá ocorrer apenas após validação funcional completa.
