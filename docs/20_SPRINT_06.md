# Sprint 06 — Frequência

## Objetivo

Implementar o controle de presença e frequência dos alunos, com registros por aula, relatórios de faltas e notificações automáticas para responsáveis quando o limite de ausências for atingido.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [ ] Professores deverão registrar presença de todos os alunos da turma de forma rápida.
- [ ] O sistema deverá calcular automaticamente o percentual de frequência por aluno.
- [ ] Alertas automáticos deverão ser enviados quando o aluno atingir 75% e 50% de frequência.
- [ ] Coordenadores deverão visualizar relatórios consolidados de frequência por turma.
- [ ] Toda operação deverá gerar auditoria e logs estruturados.

---

## Tarefas

### Módulo `attendance/`

- [ ] Criar model `AttendanceRecord` (Registro de Chamada):
  - FK para `Class`
  - FK para `Subject`
  - FK para `Teacher`
  - `date`, `lesson_number`
  - `notes` (observações da aula)
  - Herança de `BaseModel`

- [ ] Criar model `AttendanceEntry` (Presença Individual):
  - FK para `AttendanceRecord`
  - FK para `Student`
  - `status` (presente, ausente, justificado)
  - `justification` (motivo, quando justificado)
  - `justification_document` (upload de atestado)
  - Herança de `BaseModel`

- [ ] Criar model `AttendanceJustification` (Justificativa):
  - FK para `Student`
  - `start_date`, `end_date`
  - `reason`, `document`
  - `approved_by`, `approved_at`
  - `status` (pendente, aprovada, rejeitada)
  - Herança de `BaseModel`

- [ ] Implementar `AttendanceService`:
  - `open_attendance(class_id, subject_id, teacher_id, date, lesson_number, created_by)` — cria o registro da chamada
  - `record_attendance(record_id, entries_data, recorded_by)` — registra presença de todos os alunos
  - `update_entry(entry_id, status, justification, updated_by)` — corrige lançamento
  - `submit_justification(student_id, data, submitted_by)` — aluno/responsável envia justificativa
  - `approve_justification(justification_id, approved_by)` — coordenador aprova
  - `calculate_attendance_rate(student_id, class_id)` — percentual de frequência

- [ ] Implementar `AttendanceSelector`:
  - `get_class_attendance_summary(class_id, period)` — resumo por turma
  - `get_student_attendance(student_id, class_id)` — histórico de um aluno
  - `get_students_at_risk(class_id, threshold=75)` — alunos com frequência abaixo do limite
  - `get_teacher_attendance_history(teacher_id, date_range)` — chamadas lançadas

### Regras de Negócio

- [ ] O percentual mínimo de frequência deverá ser configurável por escola (padrão: 75%)
- [ ] O sistema deverá calcular dias letivos automaticamente (descontando feriados e dias não letivos do `calendar/`)
- [ ] Ao atingir 75% de frequência, deverá ser disparado um evento → notificação de alerta
- [ ] Ao atingir 50% de frequência, deverá ser disparado um evento → notificação crítica

### Celery Tasks

- [ ] Task `check_attendance_thresholds`: executada diariamente, verifica alunos em risco e dispara eventos de notificação
- [ ] Task `generate_attendance_report`: gera relatório PDF de frequência por turma ou aluno

### Frontend — Templates HTMX

- [ ] Tela de chamada: lista todos os alunos da turma com toggle presente/ausente (HTMX)
- [ ] Indicador visual de chamadas pendentes no painel do professor
- [ ] Tela de frequência do aluno (histórico por disciplina com gráfico)
- [ ] Tela de alunos em risco (filtro por turma e percentual)
- [ ] Formulário de submissão de justificativa (responsável/aluno)
- [ ] Tela de aprovação de justificativas (coordenador)

---

## Dependências

- Sprint 04 concluída: `Class`, `Student`, `Enrollment`, `Schedule`
- Sprint 05 concluída: `CalendarEvent`, `Holiday` (para cálculo de dias letivos)

---

## Definition of Done

- [ ] Todos os critérios de aceite validados
- [ ] `calculate_attendance_rate` com testes unitários cobrindo casos extremos
- [ ] Testes de integração para registro de chamada completa
- [ ] Testes para alertas de frequência
- [ ] Auditoria validada para todas as operações
- [ ] Pipeline CI passando
