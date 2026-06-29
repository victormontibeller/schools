# Sprint 06 — Frequência

## Objetivo

Implementar o controle de presença e frequência dos alunos, com registros por aula, relatórios de faltas e notificações automáticas para responsáveis quando o limite de ausências for atingido.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [x] Professores deverão registrar presença de todos os alunos da turma de forma rápida.
- [x] O sistema deverá calcular automaticamente o percentual de frequência por aluno.
- [ ] Alertas automáticos deverão ser enviados quando o aluno atingir 75% e 50% de frequência. *(evento interno classificando OK/ALERTA/CRÍTICO; envio real Sprint 07)*
- [x] Coordenadores deverão visualizar relatórios consolidados de frequência por turma.
- [x] Toda operação deverá gerar auditoria e logs estruturados.

---

## Tarefas

### Módulo `attendance/`

- [x] Criar model `AttendanceRecord` (Registro de Chamada):
  - FK para `Class`
  - FK para `Subject`
  - FK para `Teacher`
  - `date`, `lesson_number`
  - `notes` (observações da aula)
  - Herança de `BaseModel`

- [x] Criar model `AttendanceEntry` (Presença Individual):
  - FK para `AttendanceRecord`
  - FK para `Student`
  - `status` (presente, ausente, justificado)
  - `justification` (motivo, quando justificado)
  - `justification_document` *(representado pelo campo `document` em `AttendanceJustification`)*
  - Herança de `BaseModel`

- [x] Criar model `AttendanceJustification` (Justificativa):
  - FK para `Student`
  - `start_date`, `end_date`
  - `reason`, `document`
  - `approved_by`, `approved_at`
  - `status` (pendente, aprovada, rejeitada) + `rejection_reason`
  - Herança de `BaseModel`

- [x] Implementar `AttendanceService`:
  - `open_attendance(class_id, subject_id, teacher_id, date, lesson_number, created_by)` — cria o registro da chamada e pré-cadastra todos os alunos ativos como PRESENT
  - `record_attendance(record_id, entries_data, recorded_by)` — registra presença de todos os alunos (aceita `{student_id: "STATUS"}` ou `{student_id: {"status":..., "justification":...}}`)
  - `update_entry(entry_id, status, justification, updated_by)` — corrige lançamento
  - `submit_justification(student_id, data, submitted_by)` — aluno/responsável envia justificativa
  - `approve_justification(justification_id, approved_by)` — coordenador aprova
  - `reject_justification(justification_id, reason, approved_by)` — coordenador rejeita com motivo
  - `calculate_attendance_rate(student_id, class_id)` — percentual de frequência (justificados contam como presença)
  - `get_attendance_threshold(student_id, class_id)` — classifica OK/ALERTA(75)@CRÍTICO(50)

- [x] Implementar `AttendanceSelector`:
  - `list_records(class_id, teacher_id, date_from, date_to)`
  - `get_class_attendance_summary(class_id)` — resumo por aluno + lista `at_risk` (<75%)
  - `get_student_attendance(student_id, class_id)` — histórico de um aluno
  - `get_students_at_risk(class_id, threshold=75)` — alunos com frequência abaixo do limite
  - `get_teacher_attendance_history(teacher_id, date_range)` — chamadas lançadas
  - `JustificationSelector.list_justifications(status)`

### Regras de Negócio

- [ ] O percentual mínimo de frequência deverá ser configurável por escola (padrão: 75%) *(constantes `ALERT_THRESHOLD=75` e `CRITICAL_THRESHOLD=50`; parametrização por escola pendente)*
- [ ] O sistema deverá calcular dias letivos automaticamente (descontando feriados e dias não letivos do `calendar/`) *(disponível via `CalendarService.is_working_day`; integração automática com o cálculo de frequência pendente)*
- [x] Ao atingir 75% de frequência, deverá ser disparado um evento → notificação de alerta *(classificação em `get_attendance_threshold`; envio na Sprint 07)*
- [x] Ao atingir 50% de frequência, deverá ser disparado um evento → notificação crítica *(idem)*

### Celery Tasks

- [ ] Task `check_attendance_thresholds`: executada diariamente, verifica alunos em risco e dispara eventos de notificação *(envio real Sprint 07)*
- [ ] Task `generate_attendance_report`: gera relatório PDF de frequência por turma ou aluno *(pendente)*

### Frontend — Templates HTMX

- [x] Tela de chamada: lista todos os alunos da turma com toggle presente/ausente/justificado (radio groups estilo Bootstrap)
- [ ] Indicador visual de chamadas pendentes no painel do professor *(pendente)*
- [x] Tela de frequência do aluno (histórico por disciplina, com badge de % e nível)
- [x] Tela de alunos em risco (filtro por turma, badge Alerta/Crítico)
- [x] Formulário de submissão de justificativa (responsável/aluno, com upload de documento)
- [x] Tela de aprovação de justificativas (coordenador, approve/reject inline)
- [x] Resumo consolidado por turma com lista de alunos em risco no topo

---

## Dependências

- Sprint 04 concluída: `Class`, `Student`, `Enrollment`, `Schedule`
- Sprint 05 concluída: `CalendarEvent`, `Holiday` (para cálculo de dias letivos)

---

## Definition of Done

- [x] Todos os critérios de aceite validados (exceto notificação/envio — Sprint 07)
- [ ] `calculate_attendance_rate` com testes unitários cobrindo casos extremos *(pende escrever testes do app)*
- [ ] Testes de integração para registro de chamada completa *(pende escrever testes do app)*
- [ ] Testes para alertas de frequência *(pende escrever testes do app)*
- [x] Auditoria validada para todas as operações
- [ ] Pipeline CI passando *(lint verde; cobertura <80% por falta de testes do app)*

---

## Progresso

> Atualizado em 2026-06-29

**Concluído:**
- App `attendance/` criado e registrado em `TENANT_SPECIFIC_APPS`, `pytest.ini`, `pyproject.toml`, `Makefile`
- Models: `AttendanceRecord` (chamada por turma/disciplina/professor/data/aula, com `unique_together`), `AttendanceEntry` (presença individual, `unique_together` record+student, status PRESENT/ABSENT/JUSTIFIED), `AttendanceJustification` (PENDING/APPROVED/REJECTED com `approved_by`/`approved_at`, upload de documento, `rejection_reason`)
- `AttendanceService`: `open_attendance` (cria registro + bulk pré-cadastra todos os alunos ativos como PRESENT), `record_attendance` (bulk, aceita dict plano ou com justification), `update_entry`, `submit_justification`, `approve_justification`, `reject_justification`, `calculate_attendance_rate` (justificados contam como presença), `get_attendance_threshold` (classifica OK/ALERT/CRITICAL com limiares 75/50)
- `AttendanceSelector`: `list_records` (filtros turma/professor/intervalo), `get_class_attendance_summary` (resumo + lista at_risk pré-ordenada), `get_student_attendance`, `get_students_at_risk(threshold=75)`, `get_teacher_attendance_history`, `JustificationSelector.list_justifications(status)`
- Admin para os 3 models com inline de presenças no registro e `date_hierarchy`
- Forms: `AttendanceRecordForm` (ModelForm), `JustificationForm` (com upload)
- Views HTMX: lista de registros, abrir chamada, **tela de chamada bulk** (radio groups Bootstrap por aluno: Presente/Ausente/Justificado), resumo consolidado da turma (com alunos em risco banner e badge por nível), histórico do aluno, alunos em risco (filtro por turma), justificativas (lista filtrável por situação + aprovar/rejeitar inline + form com upload)
- Menu lateral + card no dashboard com link "Frequência"; URLs incluídas em `core/urls.py`
- Migrations geradas e aplicadas ao tenant `demo`; seed de demo (1 chamada em 16/03/2026 com 2 alunos: 1 presente, 1 ausente; 1 justificativa pendente "Consulta médica")
- Smoke test validado: 11 rotas retornam 200/302; `calculate_attendance_rate` confirmado (João=100%)

**Pendente:**
- Testes unitários e de integração do app (restaurar cobertura ≥80%)
- Parametrização do limiar de frequência por escola (hoje constante global)
- Cálculo automático de dias letivos integrado ao `CalendarService.is_working_day` no cálculo de frequência
- Task `check_attendance_thresholds` (diário) e `generate_attendance_report` (PDF)
- Indicador de chamadas pendentes no painel do professor
- Histórico do aluno com gráfico (hoje é tabela)
- Atualizar pipeline CI (`ci.yml`) para incluir `attendance` nos paths de lint/test
