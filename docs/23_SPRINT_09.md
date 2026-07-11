# Sprint 09 — Calendário

> **Documento histórico.** Em caso de divergência, prevalecem os documentos normativos em `docs/`.

## Objetivo

Implementar o calendário acadêmico da escola, permitindo o registro de eventos, feriados, dias letivos e datas importantes, integrando com a agenda e as notificações.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [x] O calendário deverá suportar eventos com data única e eventos recorrentes.
- [x] Feriados nacionais e dias não letivos deverão ser configuráveis por escola.
- [x] Eventos deverão ser visualizados em formato de calendário mensal.
- [ ] Criação de evento deverá disparar notificação para o público-alvo. *(evento interno; envio real na Sprint 11)*
- [x] Toda operação deverá gerar auditoria e logs estruturados.

---

## Tarefas

### Módulo `calendar/`

> **Observação:** o nome `calendar` colide com módulo da stdlib Python, então o app foi
> nomeado `academic_calendar` em código, mantendo o conceito de calendário acadêmico.

- [x] Criar model `AcademicYear` (Ano Letivo):
  - `name`, `start_date`, `end_date`
  - `status` (planejado, em andamento, encerrado)
  - FK para `School` *(via contexto de tenant)*
  - Herança de `BaseModel`

- [x] Criar model `CalendarEvent` (Evento):
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

- [x] Criar model `Holiday` (Feriado):
  - `name`, `date`
  - `type` (nacional, estadual, municipal, escolar)
  - `is_recurring` (repete todo ano)
  - Herança de `BaseModel`

- [x] Implementar `CalendarService`:
  - `create_event(data, created_by)` — dispara evento interno → notificação *(envio real na Sprint 11)*
  - `update_event(event_id, data, updated_by)`
  - `cancel_event(event_id, reason, cancelled_by)`
  - `create_holiday(data, created_by)`
  - `get_working_days(start_date, end_date)` — desconta feriados e dias não letivos
  - `is_working_day(date)` — verifica se uma data é dia letivo
  - `create_academic_year(data, created_by)`

- [x] Implementar `CalendarSelector`:
  - `get_events_by_month(year, month)`
  - `get_events_by_range(start_date, end_date, audience)`
  - `get_upcoming_events(days=7)`
  - `get_academic_year_events(academic_year_id)`
  - `HolidaySelector.list_holidays(year)` e `AcademicYearSelector.list_academic_years()`

### Frontend — Templates HTMX

- [x] Visualização de calendário mensal com navegação entre meses (HTMX)
- [ ] Modal de criação/edição de evento com seleção de audiência *(implementado como página dedicada em vez de modal)*
- [x] Lista de próximos eventos no dashboard
- [x] Tela de gestão de feriados e dias não letivos
- [x] Destaque visual por tipo de evento (cores por categoria)
- [ ] Exportação de calendário em formato iCal (.ics) *(pendente)*

### Celery Tasks

- [ ] Task `notify_upcoming_events`: enviar notificações 24h antes de eventos importantes *(envio real Sprint 11)*
- [ ] Task `generate_monthly_calendar_pdf`: exportar calendário mensal em PDF *(pendente)*

---

## Dependências

- Sprint 08 concluída: `Class`, `Teacher`, `AcademicYear`
- Sprint 11 (Comunicação) será integrada nesta Sprint para notificações — implementar evento interno apenas; o envio real será na Sprint 11

---

## Definition of Done

- [x] Todos os critérios de aceite validados (exceto notificação/envio — Sprint 11)
- [ ] `CalendarService.get_working_days` com testes unitários *(pende escrever testes do app)*
- [ ] Testes de integração para criação e consulta de eventos *(pende escrever testes do app)*
- [ ] Exportação iCal validada *(pendente)*
- [x] Auditoria validada para todas as operações
- [ ] Pipeline CI passando *(lint verde; cobertura <80% por falta de testes do app)*

---

## Progresso

> Atualizado em 2026-06-29

**Concluído:**
- App `academic_calendar/` criado (nome evita colisão com stdlib `calendar`) e registrado em `TENANT_SPECIFIC_APPS`, `pytest.ini`, `pyproject.toml`, `Makefile`
- Models: `AcademicYear` (Ano Letivo), `Holiday` (Feriado), `CalendarEvent` (Evento) com ForeignKey para `Class`, JSONField de recorrência, público-alvo, *is_public*, cancelamento
- `CalendarService`: `create_academic_year`, `create_event`, `update_event`, `cancel_event`, `create_holiday`, `is_working_day`, `get_working_days` (desconta finais de semana, feriados pontuais e recorrentes, e dias não letivos via `CalendarEvent`)
- `CalendarSelector`/`HolidaySelector`/`AcademicYearSelector`: eventos por mês (com overlap de intervalos), por intervalo, próximos N dias, por ano letivo
- Admin para os 3 models com filtros e `date_hierarchy`
- Forms: `AcademicYearForm`, `EventForm` (ModelForm), `HolidayForm`
- Views HTMX: calendário mensal navegável entre meses (partial trocada via `hx-get`/`hx-target`), detalhe do evento com cancelar, lista de próximos eventos, gestão de feriados (form + tabela), gestão de anos letivos
- Template tag `calendar_extras.get` para dict-access na grade mensal; `by_day` indexado por data
- Dashboard com widget "Próximos Eventos (7 dias)"; menu lateral com link "Calendário"
- Migrations geradas e aplicadas ao tenant `demo`; seed de demo (ano letivo 2026, 8 feriados nacionais, 2 eventos: Reunião de Pais e Festa Junina)
- Smoke test validado: 8 rotas retornam 200; `is_working_day` confirma feriado (01/05→False) e segunda útil (04/05→True)

**Pendente:**
- Testes unitários do `CalendarService`/`CalendarSelector` (restaurar cobertura ≥80%)
- Exportação iCal (.ics) e PDF mensal via Celery
- Modal de criação rápida de evento (atualmente é página dedicada)
- Atualizar pipeline CI (`ci.yml`) para incluir `academic_calendar` nos paths de lint/test
