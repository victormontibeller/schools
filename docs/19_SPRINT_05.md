# Sprint 05 — Calendário

## Objetivo

Implementar o calendário acadêmico da escola, permitindo o registro de eventos, feriados, dias letivos e datas importantes, integrando com a agenda e as notificações.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [ ] O calendário deverá suportar eventos com data única e eventos recorrentes.
- [ ] Feriados nacionais e dias não letivos deverão ser configuráveis por escola.
- [ ] Eventos deverão ser visualizados em formato de calendário mensal.
- [ ] Criação de evento deverá disparar notificação para o público-alvo.
- [ ] Toda operação deverá gerar auditoria e logs estruturados.

---

## Tarefas

### Módulo `calendar/`

- [ ] Criar model `AcademicYear` (Ano Letivo):
  - `name`, `start_date`, `end_date`
  - `status` (planejado, em andamento, encerrado)
  - FK para `School`
  - Herança de `BaseModel`

- [ ] Criar model `CalendarEvent` (Evento):
  - `title`, `description`
  - `start_date`, `end_date`
  - `start_time`, `end_time` (opcionais, para eventos com horário)
  - `type` (feriado, reunião, evento escolar, dia não letivo, avaliação, outro)
  - `recurrence` (JSONField: regra de recorrência — diária, semanal, mensal)
  - `audience` (todos, professores, alunos, responsáveis, turma específica)
  - FK para `Class` (opcional, para eventos de turma)
  - FK para `AcademicYear`
  - `is_public` (visível para responsáveis e alunos)
  - Herança de `BaseModel`

- [ ] Criar model `Holiday` (Feriado):
  - `name`, `date`
  - `type` (nacional, estadual, municipal, escolar)
  - `is_recurring` (repete todo ano)
  - Herança de `BaseModel`

- [ ] Implementar `CalendarService`:
  - `create_event(data, created_by)` — dispara evento interno → notificação
  - `update_event(event_id, data, updated_by)`
  - `cancel_event(event_id, reason, cancelled_by)`
  - `create_holiday(data, created_by)`
  - `get_working_days(start_date, end_date)` — desconta feriados e dias não letivos
  - `is_working_day(date)` — verifica se uma data é dia letivo

- [ ] Implementar `CalendarSelector`:
  - `get_events_by_month(year, month)`
  - `get_events_by_range(start_date, end_date, audience)`
  - `get_upcoming_events(days=7)`
  - `get_academic_year_events(academic_year_id)`

### Frontend — Templates HTMX

- [ ] Visualização de calendário mensal com navegação entre meses (HTMX)
- [ ] Modal de criação/edição de evento com seleção de audiência
- [ ] Lista de próximos eventos no dashboard
- [ ] Tela de gestão de feriados e dias não letivos
- [ ] Destaque visual por tipo de evento (cores por categoria)
- [ ] Exportação de calendário em formato iCal (.ics)

### Celery Tasks

- [ ] Task `notify_upcoming_events`: enviar notificações 24h antes de eventos importantes
- [ ] Task `generate_monthly_calendar_pdf`: exportar calendário mensal em PDF

---

## Dependências

- Sprint 04 concluída: `Class`, `Teacher`, `AcademicYear`
- Sprint 07 (Comunicação) será integrada nesta Sprint para notificações — implementar evento interno apenas; o envio real será na Sprint 07

---

## Definition of Done

- [ ] Todos os critérios de aceite validados
- [ ] `CalendarService.get_working_days` com testes unitários
- [ ] Testes de integração para criação e consulta de eventos
- [ ] Exportação iCal validada
- [ ] Auditoria validada para todas as operações
- [ ] Pipeline CI passando
