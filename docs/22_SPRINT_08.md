# Sprint 08 — Dashboards

## Objetivo

Implementar os dashboards da plataforma: o dashboard técnico (Grafana), o dashboard escolar (visão operacional da escola) e o dashboard executivo (visão da plataforma como produto), consolidando dados de todos os módulos anteriores.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [ ] Dashboard técnico deverá exibir métricas de infraestrutura no Grafana.
- [ ] Dashboard escolar deverá exibir KPIs em tempo real com atualização via HTMX.
- [ ] Dashboard executivo deverá exibir dados agregados de todos os Tenants.
- [ ] Todos os widgets deverão utilizar cache Redis para evitar consultas excessivas.
- [ ] Dados de dashboards deverão ser atualizados por Celery tasks periódicas.
- [ ] Toda operação deverá gerar auditoria e logs estruturados.

---

## Tarefas

### Módulo `dashboard/`

- [ ] Criar model `DashboardWidget` (configuração de widget por escola):
  - `name`, `type` (kpi, chart, table, list)
  - `datasource` (selector que alimenta o widget)
  - `refresh_interval` (em segundos)
  - `position`, `size` (layout grid)
  - FK para `School`
  - Herança de `BaseModel`

- [ ] Implementar `DashboardService`:
  - `get_school_dashboard_data(tenant)` — agrega todos os KPIs escolares
  - `get_executive_dashboard_data()` — agrega dados de todos os Tenants (schema public)
  - `invalidate_cache(tenant)` — força atualização do cache

- [ ] Implementar `DashboardSelector`:
  - `get_total_students(tenant)` — total de alunos ativos
  - `get_total_teachers(tenant)` — total de professores ativos
  - `get_today_attendance_rate(tenant)` — frequência do dia atual
  - `get_pending_activities(tenant)` — atividades com entrega próxima
  - `get_recent_announcements(tenant)` — últimos comunicados
  - `get_students_at_risk_count(tenant)` — alunos com frequência crítica
  - `get_total_tenants()` — número de escolas ativas na plataforma
  - `get_platform_growth(period)` — crescimento de tenants e usuários

### Cache de Dashboards

- [ ] Todas as consultas do `DashboardSelector` deverão ser cacheadas no Redis
- [ ] TTL configurável por tipo de dado (ex: frequência do dia = 5 min, total de alunos = 1h)
- [ ] Invalidação de cache deverá ocorrer automaticamente via eventos internos

### Celery Tasks

- [ ] Task `update_school_dashboard_cache`: executada a cada 5 minutos por Tenant ativo
- [ ] Task `update_executive_dashboard_cache`: executada a cada 15 minutos
- [ ] Task `generate_daily_summary`: gera resumo diário por escola (enviado por e-mail ao coordenador)

### Dashboard Técnico — Grafana

- [ ] Dashboard "Infraestrutura":
  - CPU, memória e disco dos containers
  - Conexões ativas ao PostgreSQL
  - Latência de requisições (p50, p95, p99)
  - Taxa de erros 4xx e 5xx

- [ ] Dashboard "Filas e Workers":
  - Tamanho das filas RabbitMQ por tipo de task
  - Workers Celery ativos e ociosos
  - Tasks processadas por minuto
  - Tasks com falha (dead letter queue)

- [ ] Dashboard "Tenants":
  - Requisições por Tenant
  - Usuários ativos por Tenant
  - Erros por Tenant

### Dashboard Escolar — Interface Django

- [ ] Tela principal do dashboard escolar com widgets:
  - Total de alunos, professores e turmas ativas (cards KPI)
  - Frequência do dia atual (percentual + barra de progresso)
  - Gráfico de frequência semanal (últimos 7 dias)
  - Lista de alunos em risco (frequência crítica)
  - Próximos eventos do calendário
  - Atividades com entrega nos próximos 3 dias
  - Últimos comunicados

- [ ] Atualização automática de KPIs via HTMX polling a cada 60 segundos
- [ ] Widgets com drill-down: clicar em "Alunos em risco" → vai para lista filtrada

### Dashboard Executivo — Interface Django

- [ ] Tela acessível apenas pelo Admin da plataforma:
  - Total de escolas ativas
  - Total de usuários por tipo (alunos, professores, responsáveis)
  - Crescimento mensal (gráfico de linha)
  - Distribuição geográfica dos Tenants
  - Taxa de utilização por funcionalidade

---

## Dependências

- Sprints 02-07 concluídas
- Grafana e Prometheus configurados na Sprint 00

---

## Definition of Done

- [ ] Todos os critérios de aceite validados
- [ ] Cache Redis validado: segunda requisição deve ser servida do cache
- [ ] Testes unitários para todos os métodos do `DashboardSelector`
- [ ] Dashboards Grafana com todos os painéis configurados
- [ ] Performance validada: dashboard escolar deverá carregar em < 1 segundo
- [ ] Pipeline CI passando
