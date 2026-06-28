# Visão do Projeto

## Missão

O projeto deverá construir uma plataforma **SaaS Multi-Tenant para Gestão Escolar** comercial, capaz de atender desde uma única escola até milhares de instituições sem necessidade de reestruturação arquitetural.

## Visão

O sistema deverá ser reconhecido como referência em gestão escolar, priorizando simplicidade, confiabilidade e evolução contínua sem mudanças estruturais.

---

## Princípios Fundamentais

Toda decisão técnica e de produto deverá seguir estes princípios:

| Princípio | Descrição |
|---|---|
| **Simplicidade** | Toda solução deverá ser a mais simples possível. |
| **Modularidade** | Cada domínio deverá ser independente. |
| **Segurança** | Segurança deverá ter prioridade sobre novas funcionalidades. |
| **Auditabilidade** | Toda alteração deverá ser auditável. |
| **Observabilidade** | Toda funcionalidade deverá produzir logs, métricas e eventos. |
| **Reutilização** | Todo código deverá ser reutilizável sempre que possível. |
| **Baixo Acoplamento** | Módulos não deverão conhecer detalhes internos uns dos outros. |
| **Alta Coesão** | Cada módulo deverá conter apenas sua própria responsabilidade. |
| **Evolução Contínua** | Toda decisão técnica deverá considerar a evolução futura. |
| **Testabilidade** | Toda regra crítica deverá ser testável de forma isolada. |

---

## Regras Invioláveis

As seguintes regras nunca poderão ser violadas:

- Nenhuma regra de negócio poderá existir em Views.
- Nenhum módulo poderá ignorar o contexto do Tenant.
- Nenhum registro poderá ser removido fisicamente.
- Nenhuma funcionalidade crítica poderá existir sem observabilidade.
- Nenhuma informação sensível poderá aparecer em logs.
- Nenhum dado poderá ser compartilhado entre Tenants.
- Toda ação importante deverá produzir um evento interno.

---

## Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.13 |
| Framework | Django |
| Frontend | Django Templates, HTMX, Alpine.js, Bootstrap |
| Banco de Dados | PostgreSQL |
| Multi-Tenant | django-tenants |
| Fila Assíncrona | Celery + RabbitMQ |
| Cache | Redis |
| Proxy / HTTPS | Traefik |
| Observabilidade | Grafana, Prometheus, Loki, OpenTelemetry |
| Containerização | Docker, Docker Compose, Docker Swarm |

---

## Visão de Longo Prazo

O projeto foi concebido para evoluir gradualmente sem mudanças estruturais. A arquitetura deverá suportar futuras funcionalidades como:

- Aplicativo móvel nativo
- Integrações com sistemas educacionais externos
- Inteligência artificial para apoio pedagógico
- Dashboards analíticos avançados
- Automações e integrações externas
- Módulo financeiro (receitas, inadimplência)

Todas essas evoluções deverão ser incorporadas preservando os princípios de simplicidade, modularidade e baixo acoplamento definidos desde o início.
