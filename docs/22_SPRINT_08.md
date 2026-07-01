# Sprint 08 — Turmas e Agenda

## Objetivo

Implementar o gerenciamento de turmas, salas, grade horária e atividades acadêmicas, permitindo que a escola estruture seu ano letivo e os professores registrem conteúdos e avaliações.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [x] Turmas deverão ser criadas com ano letivo, série, turno e professor responsável.
- [x] Alunos deverão ser matriculados em turmas com controle de vagas.
- [x] Salas deverão ser cadastradas com capacidade e recursos disponíveis.
- [x] A grade horária deverá permitir atribuição de professor, disciplina e sala por horário.
- [x] Atividades deverão ser criadas com data de entrega, tipo e valor máximo.
- [x] Toda operação deverá gerar auditoria e logs estruturados.

---

## Tarefas

### Módulo `classes/`

- [x] Criar model `Class` (Turma):
  - `name`, `grade` (série), `shift` (turno: matutino, vespertino, noturno)
  - `academic_year`
  - FK para `School`
  - `max_students` (vagas)
  - `class_teacher` (FK para `Teacher`)
  - Herança de `BaseModel`

- [x] Criar model `Enrollment` (Matrícula):
  - FK para `Student`
  - FK para `Class`
  - `enrollment_date`, `status` (ativa, transferida, cancelada)
  - Herança de `BaseModel`

- [x] Implementar `ClassService`:
  - `create_class(data, created_by)`
  - `update_class(class_id, data, updated_by)`
  - `enroll_student(class_id, student_id, enrolled_by)` — valida vagas disponíveis
  - `transfer_student(student_id, from_class_id, to_class_id, transferred_by)`
  - `unenroll_student(enrollment_id, reason, unenrolled_by)`

- [x] Implementar `ClassSelector`:
  - `list_classes(filters)`
  - `get_class_students(class_id)`
  - `get_available_classes(grade, shift)`
  - `get_enrollment_count(class_id)`

### Módulo `rooms/`

- [x] Criar model `Room` (Sala):
  - `name`, `code`
  - `capacity`
  - `type` (sala de aula, laboratório, quadra, biblioteca, etc.)
  - `resources` (JSONField: projetor, ar condicionado, etc.)
  - `floor`, `building`
  - Herança de `BaseModel`

- [x] Implementar `RoomService`:
  - `create_room(data, created_by)`
  - `update_room(room_id, data, updated_by)`
  - `check_availability(room_id, date, start_time, end_time)` — verifica conflitos

### Módulo `agenda/`

- [x] Criar model `TimeSlot` (Horário):
  - `day_of_week`, `start_time`, `end_time`, `slot_number`

- [x] Criar model `Schedule` (Grade Horária):
  - FK para `Class`
  - FK para `Teacher`
  - FK para `Subject`
  - FK para `Room`
  - FK para `TimeSlot`
  - `valid_from`, `valid_until`
  - Herança de `BaseModel`

- [x] Implementar `ScheduleService`:
  - `create_schedule(data, created_by)` — valida conflitos de professor e sala
  - `update_schedule(schedule_id, data, updated_by)`
  - `get_weekly_schedule(class_id)`
  - `get_teacher_schedule(teacher_id)`
  - `create_time_slot(data, created_by)` — gestão de faixas de horário

### Módulo `activities/`

- [x] Criar model `Activity` (Atividade/Avaliação):
  - FK para `Class`
  - FK para `Subject`
  - FK para `Teacher`
  - `title`, `description`
  - `type` (tarefa, prova, trabalho, participação)
  - `due_date`, `max_score`
  - `weight` (peso na média)
  - Herança de `BaseModel`

- [x] Criar model `ActivitySubmission` (Nota/Entrega):
  - FK para `Activity`
  - FK para `Student`
  - `score`, `submitted_at`, `feedback`
  - Herança de `BaseModel`

- [x] Implementar `ActivityService`:
  - `create_activity(data, created_by)` — envia notificação via evento
  - `update_activity(activity_id, data, updated_by)`
  - `record_score(activity_id, student_id, score, feedback, recorded_by)`
  - `batch_record_scores(activity_id, scores_data, recorded_by)`

### Frontend — Templates HTMX

- [x] Tela de gestão de turmas com lista de alunos matriculados
- [x] Formulário de matrícula com busca de aluno
- [x] Visualização da grade horária semanal (tabela por horário)
- [x] Formulário de atividade com campo de data e tipo
- [x] Tela de lançamento de notas (bulk entry com HTMX)

---

## Dependências

- Sprint 03 concluída: `Teacher`, `Student`, `Subject`

---

## Definition of Done

- [x] Todos os critérios de aceite validados
- [ ] Validação de vagas e conflitos de horário com testes unitários
- [ ] Testes de integração para matrícula e grade horária
- [x] Auditoria validada para todas as operações
- [ ] Pipeline CI passando *(lint verde; cobertura <80% por falta de testes dos apps novos)*

---

## Progresso

> Atualizado em 2026-06-29

**Concluído:**
- `classes/`: `Class`, `Enrollment`, `ClassService` (criar/atualizar/matricular/transferir/desmatricular com validação de vagas), `ClassSelector`, admin, views/forms/templates HTMX (list, create, detail com matrícula)
- `rooms/`: `Room`, `RoomService` (criar/atualizar/disponibilidade com checagem de conflito), `RoomSelector`, admin, views/forms/templates HTMX
- `agenda/`: `TimeSlot`, `Schedule`, `ScheduleService` (criar/atualizar + validação de conflito de professor e sala considerando `valid_until`), `create_time_slot`, `ScheduleSelector`/`TimeSlotSelector`, admin, views/forms/templates HTMX (grade semanal, grade do professor, gestão de horários)
- `activities/`: `Activity`, `ActivitySubmission`, `ActivityService` (criar/atualizar/record_score/batch_record_scores), `ActivitySelector`, admin, views/forms/templates HTMX (list, create, detail com lançamento de nota)
- Migrações iniciais dos 4 apps geradas e aplicadas; `core/settings.py`, `pytest.ini`, `pyproject.toml` e `Makefile` atualizados
- Bugs corrigidos: `core/urls.py` sem include dos 4 apps; `create_class` não salvava `class_teacher`; forms de Schedule/Atividade exigiam UUIDs manuais → convertidos para dropdowns; activities sem templates; gestão de TimeSlots inexistente; conflito de horário não considerava `valid_until`; variável não usada em `batch_record_scores`
- Landing page pública de vendas em `/` + dashboard autenticado em `/app/`; `base.html` com htmx e menu completo
- Ambiente de demonstração funcional: tenant `demo` + superuser + dados de exemplo (professor, 2 alunos, 2 salas, 6 horários, 1 turma, matrícula, 1 atividade); smoke tests de GET e POST validados

**Pendente:**
- Testes unitários e de integração dos 4 apps (restaurar cobertura ≥80%)
- Atualizar pipeline CI para incluir os 4 apps no lint/test paths
