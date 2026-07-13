# Arquitetura do Sistema

> **Escopo:** arquitetura, módulos e fluxo de execução. Regras de implementação ficam em `docs/03_ENGINEERING_RULES.md`; padrões de código em `docs/10_CODING_STANDARDS.md`; interface em `docs/09_UI_GUIDELINES.md`.

## Visão Geral

O projeto deverá utilizar uma arquitetura de **Monólito Modular**, permitindo evolução contínua sem a complexidade de microserviços.

Esta escolha deverá garantir:
- Simplicidade de desenvolvimento e operação
- Facilidade de debugging e rastreamento
- Transações atômicas entre módulos
- Deploy unificado e previsível
- Base sólida para uma eventual migração futura, caso necessário

---

## Stack Tecnológica

### Backend

| Tecnologia | Finalidade |
|---|---|
| Python 3.13 | Linguagem principal |
| Django | Framework web |
| Django Templates | Renderização de interfaces |
| HTMX | Interatividade sem JavaScript complexo |
| Alpine.js | Reatividade leve no frontend |
| Bootstrap | Design system e layout responsivo |

### Banco de Dados

| Tecnologia | Finalidade |
|---|---|
| PostgreSQL | Banco de dados principal |
| django-tenants | Isolamento por Schema por Tenant |

A estratégia Multi-Tenant deverá utilizar **um Schema PostgreSQL por escola (Tenant)**. Nenhum dado deverá ser compartilhado entre Tenants.

### Processamento Assíncrono

| Tecnologia | Finalidade |
|---|---|
| Celery | Processamento de tarefas assíncronas |
| RabbitMQ | Message Broker oficial do projeto |

O RabbitMQ deverá ser o único Broker do sistema. O Redis **não** deverá ser utilizado como Broker.

Tarefas assíncronas deverão incluir:
- Envio de e-mails
- Envio de mensagens WhatsApp
- Geração de relatórios
- Processamentos demorados
- Futuras tarefas de Inteligência Artificial

### Cache

| Tecnologia | Finalidade |
|---|---|
| Redis | Cache de consultas, dashboards, sessões e rate limiting |

### Infraestrutura

| Tecnologia | Finalidade |
|---|---|
| Docker | Containerização |
| Docker Compose | Orquestração para desenvolvimento |
| Docker Swarm | Orquestração para produção |
| Traefik | Reverse Proxy, HTTPS, Load Balancer e Roteamento |

### Observabilidade

| Tecnologia | Finalidade |
|---|---|
| Grafana | Visualização de dashboards técnicos |
| Prometheus | Coleta de métricas |
| Loki | Coleta e indexação de logs |
| OpenTelemetry | Instrumentação e traces distribuídos |

---

## Fluxo da Requisição

```
Cliente
  └─▶ Traefik (HTTPS + Roteamento por domínio)
        └─▶ Django (Tenant Middleware → Auth → View → Service)
              ├─▶ PostgreSQL (Schema do Tenant)
              ├─▶ Redis (Cache)
              └─▶ RabbitMQ (Eventos assíncronos)
                    └─▶ Celery Worker
                          ├─▶ E-mail
                          ├─▶ WhatsApp
                          └─▶ Relatórios
```

```
Observabilidade
  Django → OpenTelemetry → Prometheus
  Django → Loki (Logs JSON)
  Grafana ← Prometheus + Loki
```

---

## Módulos do Sistema

Cada domínio deverá possuir seu próprio módulo independente:

```
accounts/       → Usuários, autenticação, perfis e permissões
tenancy/        → Catálogo público de escolas, domínios e acessos de suporte
teachers/       → Professores e suas disciplinas
students/       → Alunos e seus dados
guardians/      → Responsáveis e vínculos com alunos
classes/        → Turmas, matrículas e ano letivo
rooms/          → Salas físicas e recursos
agenda/         → Grade horária e agendamentos
student_diary/ → Agenda da Educação Infantil, aspectos fixos da rotina e alimentação
activities/     → Atividades, avaliações e notas
attendance/     → Frequência e controle de presença
academic_calendar/ → Calendário acadêmico e eventos
enrollments/    → Matrículas, rematrículas e documentos
financeiro/     → Planos, cobranças e pagamentos
addresses/      → Endereços unificados
notifications/  → Notificações, e-mails e WhatsApp
dashboard/      → Dashboards técnico, escolar e executivo
audit/          → Auditoria de todas as ações do sistema
```

### Módulos de infraestrutura (não são Django apps)

```
base/           → Módulo Python puro: BaseModel, BaseService, BaseRepository,
                   BaseSelector, BaseValidator, exceptions, events, context vars
tenancy/        → App compartilhado: School, Domain e SupportAccessGrant
core/           → Configuração e app presente em cada schema: Role, CustomUser,
                   BusinessUnit, settings, middleware, urls, wsgi, asgi, celery
```

Cada módulo deverá conter **apenas sua própria responsabilidade**. Dependências entre módulos deverão ocorrer apenas via interfaces explícitas, nunca via acesso direto a modelos internos.

> **Regra de dependência:** `base` não conhece nenhum app Django. Todos os apps importam de `base`. Apenas `audit.services` pode ser importado por `base.services` e somente via import lazy (evita circular dep).

---

## Estrutura Interna de Cada Módulo

Todo módulo deverá seguir estrutura **plana** — arquivos únicos, sem sub-pacotes:

```
<modulo>/
  __init__.py
  apps.py
  models.py      → Modelos de dados (herdam de base.models.BaseModel)
  services.py    → Regras de negócio (única fonte de verdade)
  selectors.py   → Consultas somente-leitura
  forms.py       → Formulários Django
  views.py       → Orquestração apenas (sem lógica de negócio)
  urls.py        → Rotas do módulo
  admin.py       → Django Admin
  tasks.py       → Tarefas Celery (quando aplicável)
  tests/
    __init__.py
    test_<nome>.py
  templates/<modulo>/
    *.html
    partials/
```

> **Regra:** Nunca criar `services/`, `models/`, `repositories/` como sub-pacote. Um arquivo por camada. Se um arquivo crescer além de 400 linhas, é sinal de que o domínio precisa de um novo app, não de um sub-pacote.

## Identidade entre schemas

- `School`, `Domain` e `SupportAccessGrant` existem somente no `public`.
- `CustomUser`, `Role`, auth e sessions existem no `public` e separadamente em cada tenant.
- O domínio resolve o schema antes da autenticação; o mesmo e-mail pode existir em escolas
  diferentes sem compartilhar senha, sessão ou permissões.
- Operadores do `public` acessam tenants apenas por token temporário, de uso único e auditado.
- A conta técnica de suporte não possui senha utilizável e registra o operador público real.

### Responsabilidades por Camada

| Arquivo | Responsabilidade |
|---|---|
| `models.py` | Definição das entidades e persistência no banco de dados |
| `services.py` | Toda regra de negócio do módulo. Única camada que altera estado |
| `selectors.py` | Consultas de leitura complexas, filtros e paginação |
| `forms.py` | Validação e limpeza dos dados vindos da interface |
| `views.py` | Apenas orquestração: receber request → chamar service → retornar response |
| `admin.py` | Configuração do Django Admin para o módulo |
| `tasks.py` | Tarefas Celery para operações assíncronas |

---

## Sistema de Eventos

Toda ação importante deverá produzir um evento interno.

Fluxo de eventos:

```
Ação (ex: Aluno criado)
  └─▶ Service dispara evento
        ├─▶ Auditoria registra a operação
        ├─▶ Dashboard atualiza métricas
        ├─▶ Notificação é criada
        │     ├─▶ E-mail enviado via Celery
        │     └─▶ WhatsApp enviado via Celery
        └─▶ Log estruturado emitido
```

Essa estratégia deverá reduzir acoplamento e facilitar a adição de novas funcionalidades sem alterar código existente.

---

## Dashboards

A arquitetura deverá suportar três tipos de dashboard desde o início:

### Dashboard Técnico (Grafana)
- Uso de CPU e memória
- Estado do banco de dados
- Filas do RabbitMQ
- Workers Celery
- Latência das requisições

### Dashboard Escolar
- Total de alunos e professores
- Frequência do dia
- Atividades pendentes
- Comunicados recentes

### Dashboard Executivo
- Número de escolas ativas
- Crescimento de usuários
- Taxa de utilização por tenant
- Receita (implementação futura)
