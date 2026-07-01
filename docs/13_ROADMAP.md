# Roadmap

## Visão Geral

O desenvolvimento deverá ser organizado em **Sprints de 2 semanas** cada.

Cada Sprint deverá entregar valor incrementável e funcional, com toda a infraestrutura de observabilidade e auditoria aplicada desde o início.

A ordem abaixo e a referencia oficial para planejamento e execucao das Sprints.

---

## Sprints

| Sprint | Nome | Objetivo Principal |
|---|---|---|
| **Sprint 00** | Infraestrutura | Ambiente completo: banco, cache, filas, observabilidade e Django base |
| **Sprint 01** | Arquitetura Base | Padrões de código: BaseModel, Services, Audit, Middleware, Logging |
| **Sprint 02** | Contas e Autenticação | Usuários, login, permissões, perfis e base de schools |
| **Sprint 03** | Cadastros Principais | Professores, alunos e responsáveis |
| **Sprint 04** | Enderecos Unificados | Centralizar cadastro de enderecos para school, teacher, student e guardian |
| **Sprint 05** | Identificacao Cadastral | Padronizar dados pessoais e documentos de guardian, student e teacher |
| **Sprint 06** | Tela da Empresa | Criar a interface de cadastro e edicao da escola com dados institucionais e responsavel |
| **Sprint 07** | Frontend de Disciplinas | Criar a interface completa de subjects com listagem, cadastro e edicao |
| **Sprint 08** | Turmas e Agenda | Turmas, salas, grade horária e atividades |
| **Sprint 09** | Calendário | Calendário acadêmico, eventos e feriados |
| **Sprint 10** | Frequência | Controle de presença e relatórios de falta |
| **Sprint 11** | Comunicação | Notificações, e-mail e WhatsApp |
| **Sprint 12** | Dashboards | Dashboard técnico, escolar e executivo |
| **Sprint 13** | Padrao de Listagens | Unificar botao adicionar, busca e contador de registros em todas as telas |
| **Sprint 14** | UX e Produtividade | Melhorar usabilidade, fluxo de formulários e velocidade operacional |
| **Sprint 15** | Qualidade e Testes | Elevar cobertura, reduzir regressões e padronizar contratos |
| **Sprint 16** | Matrícula e Secretaria | Digitalizar processo de matrícula, rematrícula e documentação escolar |
| **Sprint 17** | Financeiro Escolar | Cobranças, inadimplência, conciliação e relatórios financeiros básicos |
| **Sprint 18** | IA | Inteligência artificial para apoio pedagógico |
| **Sprint 19** | Segurança e LGPD+ | Fortalecer proteção de dados, rastreabilidade e resposta a incidentes |
| **Sprint 20** | Produção | Docker Swarm, hardening, performance e monitoramento |

---

## Fases Sugeridas

| Fase | Sprints |
|---|---|
| **Fundacao** | 00, 01, 02, 03 |
| **Cadastro e Base Operacional** | 04, 05, 06, 07, 08, 09, 10 |
| **Comunicacao e Visao Gerencial** | 11, 12, 13, 14 |
| **Robustez e Expansao** | 15, 16, 17, 18, 19 |
| **Entrega Final** | 20 |

---

## Princípios do Roadmap

- Toda Sprint deverá incluir observabilidade e auditoria no escopo de cada entrega.
- Nenhuma Sprint poderá ser concluída sem passar pelo **Definition of Done**.
- O backlog poderá ser ajustado, mas a ordem das Sprints 00 e 01 é imutável.
- A Sprint 20 (Produção) deverá ocorrer apenas ao final, após validacao funcional e operacional completa.
- As Sprints 11+ deverão ser priorizadas conforme impacto operacional, risco e esforço.
