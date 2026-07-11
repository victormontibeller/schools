# Sprint 03 — Cadastros Principais

> **Documento histórico.** Em caso de divergência, prevalecem os documentos normativos em `docs/`.

## Objetivo

Implementar os módulos de cadastro dos atores principais da plataforma: professores, alunos e responsáveis. Estes módulos formam o núcleo de dados do sistema escolar.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [x] Professores deverão ser cadastrados, editados e desativados com Soft Delete.
- [x] Alunos deverão ser cadastrados com dados completos e vinculados a responsáveis.
- [x] Responsáveis deverão ser cadastrados e vinculados a um ou mais alunos.
- [ ] Professores, alunos e responsáveis deverão permitir upload de foto com armazenamento seguro.
- [x] Toda operação deverá gerar registro de auditoria.
- [x] Toda listagem deverá suportar paginação, busca e filtros.
- [x] Interface deverá utilizar HTMX para atualizações parciais sem reload.

---

## Tarefas

### Módulo `teachers/`

- [x] Criar model `Teacher` com:
  - FK para `CustomUser`
  - `subjects` (ManyToMany para disciplinas)
  - `registration_number` (matrícula interna)
  - `hire_date`
  - `photo` (upload seguro)
  - Herança de `BaseModel`

- [x] Criar model `Subject` (disciplina):
  - `name`, `code`, `workload`
  - Herança de `BaseModel`

- [x] Implementar `TeacherService`:
  - `create_teacher(data, created_by)`
  - `update_teacher(teacher_id, data, updated_by)`
  - `deactivate_teacher(teacher_id, deleted_by)`
  - `assign_subject(teacher_id, subject_id, assigned_by)`
  - `remove_subject(teacher_id, subject_id, removed_by)`

- [x] Implementar `TeacherSelector`:
  - `list_teachers(filters, paginator)`
  - `get_teacher_by_id(teacher_id)`
  - `list_teacher_subjects(teacher_id)`

### Módulo `students/`

- [x] Criar model `Student` com:
  - FK para `CustomUser` (opcional — aluno pode não ter acesso ao sistema)
  - `enrollment_number` (matrícula)
  - `birth_date`, `gender`
  - `blood_type`
  - `special_needs` (JSONField)
  - `photo` (upload seguro)
  - Herança de `BaseModel`

- [x] Implementar `StudentService`:
  - `create_student(data, created_by)`
  - `update_student(student_id, data, updated_by)`
  - `deactivate_student(student_id, deleted_by)`
  - `restore_student(student_id, restored_by)`

- [x] Implementar `StudentSelector`:
  - `list_students(filters, paginator)`
  - `get_student_by_id(student_id)`
  - `get_student_by_enrollment(enrollment_number)`

### Módulo `guardians/`

- [x] Criar model `Guardian` com:
  - FK para `CustomUser`
  - `relationship_type` (mãe, pai, avô/avó, responsável legal, etc.)
  - `cpf`, `rg`
  - `phone`, `phone_whatsapp`
  - `photo` (upload seguro)
  - Herança de `BaseModel`

- [x] Criar model `StudentGuardian` (vínculo aluno-responsável):
  - FK para `Student`
  - FK para `Guardian`
  - `is_primary` (responsável principal)
  - `has_custody` (tem guarda legal)
  - `can_pickup` (autorizado a buscar)
  - Herança de `BaseModel`

- [x] Implementar `GuardianService`:
  - `create_guardian(data, created_by)`
  - `update_guardian(guardian_id, data, updated_by)`
  - `link_student(guardian_id, student_id, data, linked_by)`
  - `unlink_student(guardian_id, student_id, unlinked_by)`

### Frontend — Templates HTMX

- [x] Listagem de professores com filtros, paginação e busca
- [ ] Formulário de cadastro/edição de professor com upload de foto
- [x] Listagem de alunos com filtros, paginação e busca
- [ ] Formulário de cadastro/edição de aluno com upload de foto
- [ ] Formulário de cadastro/edição de responsável com upload de foto
- [x] Componente de vínculo aluno-responsável inline
- [x] Tela de perfil do aluno com dados de responsáveis vinculados

### Uploads de Imagem

- [ ] Padronizar upload de foto para `Teacher`, `Student` e `Guardian`
- [ ] Validar tipo e tamanho de arquivo no frontend e backend
- [ ] Exibir preview da imagem atual quando houver foto cadastrada
- [ ] Definir fallback visual quando a entidade não possuir foto

### Importação em Lote (básico)

- [x] Suporte a importação via CSV para alunos
- [x] Validação linha a linha com relatório de erros
- [x] Processamento via Celery task (assíncrono)

---

## Dependências

- Sprint 02 concluída: `CustomUser`, `School`, autenticação

---

## Definition of Done

- [x] Todos os critérios de aceite validados
- [x] Services com testes unitários cobrindo regras de negócio
- [x] Testes de integração para vínculo aluno-responsável
- [x] Auditoria validada para todas as operações
- [x] Pipeline CI passando

---

## Progresso

> Atualizado em 2026-06-29

**Concluído:**
- `teachers/` completo: `Teacher`, `Subject`, `TeacherService`, `TeacherSelector`, admin, templates (list/detail com HTMX)
- `students/` completo: `Student`, `StudentService`, `StudentSelector`, admin, templates (list/form/profile com HTMX)
- `guardians/` completo: `Guardian`, `StudentGuardian`, `GuardianService`, admin, templates (list/detail com HTMX)
- Importação CSV de alunos via Celery task com validação linha a linha (`students/tasks.py`)
- 101 testes passando (Sprint 00–04); cobertura dos módulos Sprint 03 ≥ 86%

**Pendente:**
- Formulário de cadastro/edição de professor com upload de foto (frontend)
- Upload de foto para aluno e responsável nos formulários e telas de detalhe
