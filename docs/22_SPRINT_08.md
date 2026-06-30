# Sprint 08 — Dashboards

## Objetivo

Implementar os dashboards da plataforma: o dashboard técnico (Grafana), o dashboard escolar (visão operacional da escola) e o dashboard executivo (visão da plataforma como produto), consolidando dados de todos os módulos anteriores.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [ ] Dashboard técnico deverá exibir métricas de infraestrutura no Grafana. *(bloqueado — Sprint 00)**
- [x] Dashboard escolar deverá exibir KPIs em tempo real com atualização via HTMX.
- [x] Dashboard executivo deverá exibir dados agregados de todos os Tenants.
- [x] Todos os widgets deverão utilizar cache Redis para evitar consultas excessivas.
- [x] Dados de dashboards deverão ser atualizados por Celery tasks periódicas.
- [x] Toda operação deverá gerar auditoria e logs estruturados.

---

## Tarefas

### Módulo `dashboard/`

- [x] Criar model `DashboardWidget` (configuração de widget por escola):
  - `name`, `widget_type` (kpi, chart, table, list)
  - `datasource` (selector que alimenta o widget)
  - `refresh_interval` (em segundos)
  - `position`, `size` (layout grid)
  - `is_visible`, `config` (JSON extra)
  - Herança de `BaseModel`

- [x] Implementar `DashboardService`:
  - `get_school_dashboard_data()` — agrega todos os KPIs escolares com cache
  - `get_executive_dashboard_data()` — agrega dados de todos os Tenants com cache
  - `invalidate_cache(key)` — força atualização do cache

- [x] Implementar `DashboardSelector`:
  - `get_total_students()` — total de alunos ativos
  - `get_total_teachers()` — total de professores ativos
  - `get_total_classes()` — total de turmas ativas
  - `get_total_guardians()` — total de responsáveis ativos
  - `get_today_attendance_rate()` — frequência do dia atual
  - `get_weekly_attendance()` — frequência dos últimos 7 dias
  - `get_students_at_risk_count()` — alunos com frequência crítica
  - `get_pending_activities(days)` — atividades com entrega próxima
  - `get_upcoming_events(days)` — próximos eventos do calendário
  - `get_recent_announcements(limit)` — últimos comunicados
  - `get_total_tenants()` — número de escolas ativas na plataforma
  - `get_platform_users()` — total de usuários por tipo
  - `get_platform_growth(months)` — crescimento de tenants e usuários

### Cache de Dashboards

- [x] Todas as consultas do `DashboardSelector` com cache Redis (`DashboardService._cached()`)
- [x] TTL configurável por tipo de dado (ex: `today_attendance = 300s`, `total_students = 1h`)
- [x] Invalidação de cache via `DashboardService.invalidate_cache()`

### Celery Tasks

- [x] Task `update_school_dashboard_cache` — executada a cada 5 minutos
- [x] Task `update_executive_dashboard_cache` — executada a cada 15 minutos
- [ ] Task `generate_daily_summary` — resumo diário por escola (pendente: Sprint 09)

### Dashboard Técnico — Grafana

- [ ] *(bloqueado por Sprint 00 — Prometheus/Grafana/Loki não configurados)*

### Dashboard Escolar — Interface Django

- [x] Tela principal do dashboard escolar com widgets:
  - Total de alunos, professores, turmas e alunos em risco (cards KPI)
  - Frequência do dia atual (percentual + barra de progresso)
  - Gráfico de frequência semanal (últimos 7 dias — barras)
  - Lista de alunos em risco (drill-down para lista filtrada)
  - Próximos eventos do calendário
  - Atividades com entrega nos próximos 3 dias
  - Últimos comunicados
- [x] Atualização automática de KPIs via HTMX polling a cada 60 segundos
- [x] Widgets com drill-down: "Ver lista" para alunos em risco

### Dashboard Executivo — Interface Django

- [x] Tela acessível apenas pelo Admin da plataforma (`@staff_member_required`):
  - Total de escolas ativas (card KPI)
  - Total de usuários por tipo (tabela)
  - Crescimento mensal (últimos 6 meses)

---

## Dependências

- Sprints 02-07 concluídas
- Grafana e Prometheus configurados na Sprint 00 *(bloqueio parcial)*

---

## Definition of Done

- [x] Todos os critérios de aceite validados (exceto Grafana — bloqueado)
- [x] Cache Redis validado: segunda requisição servida do cache
- [x] Testes unitários para todos os métodos do `DashboardSelector`
- [x] Testes do `DashboardService` com cache
- [x] Testes das views
- [ ] Dashboards Grafana configurados *(bloqueado por Sprint 00)*
- [x] Pipeline CI passando

---

## Progresso

> Atualizado em 2026-06-29

**Concluído:**
- Model: `DashboardWidget`
- `DashboardSelector` — 13 métodos de KPI
- `DashboardService` — cache Redis com TTL por tipo, invalidação
- Celery tasks: `update_school_dashboard_cache`, `update_executive_dashboard_cache`
- Dashboard escolar: view + template com HTMX polling 60s
- Dashboard executivo: view admin-only com dados agregados
- 333 testes, cobertura 80.35%
- Ruff + Black passando

**Pendente (bloqueado por Sprint 00):**
- Dashboard técnico Grafana (Prometheus/Grafana/Loki pendentes)
- `generate_daily_summary` Celery task (depende de envio de email)

**Pendente (melhorias futuras):**
- Widgets configuráveis por escola via Admin (model `DashboardWidget` existe, CRUD pendente)
- Gráficos interativos (Chart.js ou similar)
- Distribuição geográfica dos tenants (precisa GeoIP ou campo de endereço)
