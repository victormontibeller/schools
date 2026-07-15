# Arquitetura do Sistema

> **Escopo:** arquitetura, módulos e fluxo de execução. Regras de implementação ficam em `docs/03_ENGINEERING_RULES.md`; padrões de código em `docs/10_CODING_STANDARDS.md`; interface em `docs/09_UI_GUIDELINES.md`.
>
> **Estado em 2026-07-13:** monólito modular, schemas, camadas e contratos estritos de importação
> estão implementados. Suporte cross-schema foi adiado e não existe no produto atual.

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
| Redis | Cache de consultas, dashboards e rate limiting |

Sessões web usam `django.contrib.sessions.backends.db`; como `sessions` está presente em cada
schema, a identidade permanece isolada por tenant.

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
tenancy/        → Catálogo público de escolas e domínios
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
tenancy/        → App compartilhado: School e Domain
core/           → Configuração e app presente em cada schema: Role, CustomUser,
                   BusinessUnit, settings, middleware, urls, wsgi, asgi, celery
```

Cada módulo deverá conter **apenas sua própria responsabilidade**. Dependências entre módulos deverão ocorrer apenas via interfaces explícitas, nunca via acesso direto a modelos internos.

> **Regra de dependência:** `base` não conhece nenhum app Django. Auditoria e autorização entram
> por portas registradas pelos adaptadores do `core` durante a inicialização.

---

## Estrutura Interna de Cada Módulo

Módulos simples seguem estrutura plana. Domínios coesos que excedam 400 linhas podem usar
pacotes Python internos aprovados no ADR-0009, mantendo os imports públicos como fachada:

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

Pacotes internos autorizados são: financeiro (planos, cobranças, pagamentos e políticas), core
(páginas públicas, saúde, escolas e unidades), atividades (atividades, notas e grupos) e
matrículas (solicitações, documentos e rematrículas). Um arquivo novo deve permanecer abaixo de
400 linhas. Não existem composition roots dispensados das regras de importação.

O CI executa `scripts/check_import_contracts.py` e exige zero violações: ORM em views, SQL direto,
dependência de `base` para apps e import direto de modelos entre domínios sempre falham.

## Identidade entre schemas

- `School` e `Domain` existem somente no `public`.
- `CustomUser`, `Role`, auth e sessions existem no `public` e separadamente em cada tenant.
- O domínio resolve o schema antes da autenticação; o mesmo e-mail pode existir em escolas
  diferentes sem compartilhar senha, sessão ou permissões.
- Operadores do `public` administram escolas e operadores sem acesso ou impersonação de tenants.

## Autorização escolar

- `RoleModuleAccess` guarda a matriz tenant-specific dos cinco papéis configuráveis. Administrador
  permanece irrestrito e não possui configuração própria.
- O catálogo de `core.access_catalog` é a fonte dos módulos, departamentos, ações suportadas,
  defaults e limites seguros de Professor e Responsável.
- `can_access(user, module, action)` é usado por middleware, services, navegação e templates.
  Visualizar, Cadastrar, Editar e Desativar são as únicas ações públicas; comandos de workflow
  como aprovar, cancelar, lançar e reconciliar pertencem a Editar.
- Módulos e ações desconhecidos são negados. O checker exige que novos apps com views ou services
  estejam ligados ao catálogo de autorização.
- O bootstrap cria somente papéis e módulos ausentes. Seeds e migrations nunca sobrescrevem
  configurações existentes do tenant.
- A Central apresenta todos os grupos em uma única matriz e salva o conjunto atomicamente. As
  versões dos cinco papéis são verificadas antes da primeira escrita; conflito em qualquer papel
  impede a atualização completa e reenvio sem mudança não gera versão nem auditoria.

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
