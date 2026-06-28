# Sprint 04 — Turmas e Agenda

## Objetivo

Implementar o gerenciamento de turmas, salas, grade horária e atividades acadêmicas, permitindo que a escola estruture seu ano letivo e os professores registrem conteúdos e avaliações.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [ ] Turmas deverão ser criadas com ano letivo, série, turno e professor responsável.
- [ ] Alunos deverão ser matriculados em turmas com controle de vagas.
- [ ] Salas deverão ser cadastradas com capacidade e recursos disponíveis.
- [ ] A grade horária deverá permitir atribuição de professor, disciplina e sala por horário.
- [ ] Atividades deverão ser criadas com data de entrega, tipo e valor máximo.
- [ ] Toda operação deverá gerar auditoria e logs estruturados.

---

## Tarefas

### Módulo `classes/`

- [ ] Criar model `Class` (Turma):
  - `name`, `grade` (série), `shift` (turno: matutino, vespertino, noturno)
  - `academic_year`
  - FK para `School`
  - `max_students` (vagas)
  - `class_teacher` (FK para `Teacher`)
  - Herança de `BaseModel`

- [ ] Criar model `Enrollment` (Matrícula):
  - FK para `Student`
  - FK para `Class`
  - `enrollment_date`, `status` (ativa, transferida, cancelada)
  - Herança de `BaseModel`

- [ ] Implementar `ClassService`:
  - `create_class(data, created_by)`
  - `update_class(class_id, data, updated_by)`
  - `enroll_student(class_id, student_id, enrolled_by)` — valida vagas disponíveis
  - `transfer_student(student_id, from_class_id, to_class_id, transferred_by)`
  - `unenroll_student(enrollment_id, reason, unenrolled_by)`

- [ ] Implementar `ClassSelector`:
  - `list_classes(filters)`
  - `get_class_students(class_id)`
  - `get_available_classes(grade, shift)`
  - `get_enrollment_count(class_id)`

### Módulo `rooms/`

- [ ] Criar model `Room` (Sala):
  - `name`, `code`
  - `capacity`
  - `type` (sala de aula, laboratório, quadra, biblioteca, etc.)
  - `resources` (JSONField: projetor, ar condicionado, etc.)
  - `floor`, `building`
  - Herança de `BaseModel`

- [ ] Implementar `RoomService`:
  - `create_room(data, created_by)`
  - `update_room(room_id, data, updated_by)`
  - `check_availability(room_id, date, start_time, end_time)` — verifica conflitos

### Módulo `agenda/`

- [ ] Criar model `TimeSlot` (Horário):
  - `day_of_week`, `start_time`, `end_time`, `slot_number`

- [ ] Criar model `Schedule` (Grade Horária):
  - FK para `Class`
  - FK para `Teacher`
  - FK para `Subject`
  - FK para `Room`
  - FK para `TimeSlot`
  - `valid_from`, `valid_until`
  - Herança de `BaseModel`

- [ ] Implementar `ScheduleService`:
  - `create_schedule(data, created_by)` — valida conflitos de professor e sala
  - `update_schedule(schedule_id, data, updated_by)`
  - `get_weekly_schedule(class_id)`
  - `get_teacher_schedule(teacher_id)`

### Módulo `activities/`

- [ ] Criar model `Activity` (Atividade/Avaliação):
  - FK para `Class`
  - FK para `Subject`
  - FK para `Teacher`
  - `title`, `description`
  - `type` (tarefa, prova, trabalho, participação)
  - `due_date`, `max_score`
  - `weight` (peso na média)
  - Herança de `BaseModel`

- [ ] Criar model `ActivitySubmission` (Nota/Entrega):
  - FK para `Activity`
  - FK para `Student`
  - `score`, `submitted_at`, `feedback`
  - Herança de `BaseModel`

- [ ] Implementar `ActivityService`:
  - `create_activity(data, created_by)` — envia notificação via evento
  - `update_activity(activity_id, data, updated_by)`
  - `record_score(activity_id, student_id, score, feedback, recorded_by)`
  - `batch_record_scores(activity_id, scores_data, recorded_by)`

### Frontend — Templates HTMX

- [ ] Tela de gestão de turmas com lista de alunos matriculados
- [ ] Formulário de matrícula com busca de aluno
- [ ] Visualização da grade horária semanal (tabela por horário)
- [ ] Formulário de atividade com campo de data e tipo
- [ ] Tela de lançamento de notas (bulk entry com HTMX)

---

## Dependências

- Sprint 03 concluída: `Teacher`, `Student`, `Subject`

---

## Definition of Done

- [ ] Todos os critérios de aceite validados
- [ ] Validação de vagas e conflitos de horário com testes unitários
- [ ] Testes de integração para matrícula e grade horária
- [ ] Auditoria validada para todas as operações
- [ ] Pipeline CI passando
