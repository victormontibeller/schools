# Sprint 03 — Cadastros Principais

## Objetivo

Implementar os módulos de cadastro dos atores principais da plataforma: professores, alunos e responsáveis. Estes módulos formam o núcleo de dados do sistema escolar.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [ ] Professores deverão ser cadastrados, editados e desativados com Soft Delete.
- [ ] Alunos deverão ser cadastrados com dados completos e vinculados a responsáveis.
- [ ] Responsáveis deverão ser cadastrados e vinculados a um ou mais alunos.
- [ ] Toda operação deverá gerar registro de auditoria.
- [ ] Toda listagem deverá suportar paginação, busca e filtros.
- [ ] Interface deverá utilizar HTMX para atualizações parciais sem reload.

---

## Tarefas

### Módulo `teachers/`

- [ ] Criar model `Teacher` com:
  - FK para `CustomUser`
  - `subjects` (ManyToMany para disciplinas)
  - `registration_number` (matrícula interna)
  - `hire_date`
  - Herança de `BaseModel`

- [ ] Criar model `Subject` (disciplina):
  - `name`, `code`, `workload`
  - Herança de `BaseModel`

- [ ] Implementar `TeacherService`:
  - `create_teacher(data, created_by)`
  - `update_teacher(teacher_id, data, updated_by)`
  - `deactivate_teacher(teacher_id, deleted_by)`
  - `assign_subject(teacher_id, subject_id, assigned_by)`
  - `remove_subject(teacher_id, subject_id, removed_by)`

- [ ] Implementar `TeacherSelector`:
  - `list_teachers(filters, paginator)`
  - `get_teacher_by_id(teacher_id)`
  - `list_teacher_subjects(teacher_id)`

### Módulo `students/`

- [ ] Criar model `Student` com:
  - FK para `CustomUser` (opcional — aluno pode não ter acesso ao sistema)
  - `enrollment_number` (matrícula)
  - `birth_date`, `gender`
  - `blood_type`
  - `special_needs` (JSONField)
  - `photo` (upload seguro)
  - Herança de `BaseModel`

- [ ] Implementar `StudentService`:
  - `create_student(data, created_by)`
  - `update_student(student_id, data, updated_by)`
  - `deactivate_student(student_id, deleted_by)`
  - `restore_student(student_id, restored_by)`

- [ ] Implementar `StudentSelector`:
  - `list_students(filters, paginator)`
  - `get_student_by_id(student_id)`
  - `get_student_by_enrollment(enrollment_number)`

### Módulo `guardians/`

- [ ] Criar model `Guardian` com:
  - FK para `CustomUser`
  - `relationship_type` (mãe, pai, avô/avó, responsável legal, etc.)
  - `cpf`, `rg`
  - `phone`, `phone_whatsapp`
  - Herança de `BaseModel`

- [ ] Criar model `StudentGuardian` (vínculo aluno-responsável):
  - FK para `Student`
  - FK para `Guardian`
  - `is_primary` (responsável principal)
  - `has_custody` (tem guarda legal)
  - `can_pickup` (autorizado a buscar)
  - Herança de `BaseModel`

- [ ] Implementar `GuardianService`:
  - `create_guardian(data, created_by)`
  - `update_guardian(guardian_id, data, updated_by)`
  - `link_student(guardian_id, student_id, data, linked_by)`
  - `unlink_student(guardian_id, student_id, unlinked_by)`

### Frontend — Templates HTMX

- [ ] Listagem de professores com filtros, paginação e busca
- [ ] Formulário de cadastro/edição de professor com upload de foto
- [ ] Listagem de alunos com filtros, paginação e busca
- [ ] Formulário de cadastro/edição de aluno
- [ ] Componente de vínculo aluno-responsável inline
- [ ] Tela de perfil do aluno com dados de responsáveis vinculados

### Importação em Lote (básico)

- [ ] Suporte a importação via CSV para alunos
- [ ] Validação linha a linha com relatório de erros
- [ ] Processamento via Celery task (assíncrono)

---

## Dependências

- Sprint 02 concluída: `CustomUser`, `School`, autenticação

---

## Definition of Done

- [ ] Todos os critérios de aceite validados
- [ ] Services com testes unitários cobrindo regras de negócio
- [ ] Testes de integração para vínculo aluno-responsável
- [ ] Auditoria validada para todas as operações
- [ ] Pipeline CI passando
