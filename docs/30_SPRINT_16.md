# Sprint 16 — Matricula e Secretaria

## Objetivo

Digitalizar o ciclo de secretaria escolar com foco em pre-matricula, matricula, rematricula, transferencia e controle documental.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [x] Fluxo de pre-matricula devera permitir cadastro inicial e acompanhamento de status.
- [x] Processo de matricula devera validar vagas por turma e periodo.
- [x] Rematricula em lote devera estar disponivel por ano letivo.
- [x] Transferencia interna e externa devera registrar historico completo.
- [x] Pendencias documentais deverao ser rastreadas por aluno.

---

## Tarefas

### Processo de Matricula

- [x] Criar estados de processo: pre_matricula, em_analise, aprovado, matriculado, recusado.
- [x] Implementar service para consolidar regras de aceite e vagas.
- [x] Criar selector para fila de analise por prioridade.

### Rematricula e Transferencia

- [x] Criar fluxo anual de rematricula por turma.
- [x] Implementar transferencia entre turmas com auditoria.
- [x] Implementar transferencia de escola com encerramento controlado.

### Documentacao

- [x] Registrar checklist documental por aluno.
- [x] Notificar pendencias documentais por canal configurado.
- [x] Adicionar filtros de pendencia no painel da secretaria.

### Interface de Secretaria

- [x] Criar tela unica de operacao com tabs por etapa do processo.
- [x] Adicionar atalhos para aprovar, rejeitar e solicitar correcoes.
- [x] Suportar busca rapida por nome, numero de matricula e responsavel.

---

## Dependencias

- Sprints 03 e 04 concluidas
- Regras academicas basicas de turma e capacidade ativas

---

## Definition of Done

- [x] Criterios de aceite validados
- [x] Regras de matricula cobertas por testes de servico
- [x] Fluxos de secretaria cobertos por testes de view
- [x] Auditoria presente em toda escrita

---

## Implementacao — App `enrollments`

### Models (`enrollments/models.py`)

- `EnrollmentApplication` — fluxo completo de matricula (PRE_ENROLLMENT → UNDER_REVIEW → APPROVED → ENROLLED / REJECTED / CANCELLED)
- `StudentDocument` — checklist documental por aluno com tipos e estados (PENDING → SUBMITTED → VERIFIED / REJECTED)

### Services (`enrollments/services.py`)

- `EnrollmentApplicationService` — create_application, submit_for_review, approve, reject, request_correction, complete_enrollment, bulk_reenroll, cancel
- `StudentDocumentService` — add_document, verify_document, reject_document

### Selectors (`enrollments/selectors.py`)

- `EnrollmentApplicationSelector` — list_by_status, list_pending_review, search_by_name, get_application_by_id, get_documents, get_student_pending_documents

### Views (`enrollments/views.py`)

- `secretary_dashboard` — tela unica com tabs (Pre-Matricula, Em Analise, Aprovados, Matriculados, Recusados)
- `application_create` / `application_detail` / `application_review` — fluxo de criacao e revisao
- `application_complete_enrollment` — efetivar matricula (cria `classes.Enrollment`)
- `application_cancel` — cancelar solicitacao
- `bulk_reenroll_view` — rematricula em lote
- `document_add` / `document_verify` / `document_reject` — gestao documental
- `notify_pending_documents` — dispara notificacao Celery

### Templates

- `secretary_dashboard.html` — layout com tabs HTMX e busca
- `application_form.html` / `application_detail.html` / `application_review.html` — telas do fluxo
- `bulk_reenroll.html` / `document_form.html` — formularios auxiliares
- `partials/applications_table.html` — tabela paginada com HTMX

### Tasks (`enrollments/tasks.py`)

- `send_pending_documents_notification` — notifica aluno/responsavel sobre pendencias documentais via email

### Testes

- 18 testes de servico (criacao, fluxo completo, rematricula, documentos)
- 11 testes de view (dashboard, criacao, revisao, efetivacao, rematricula em lote)
- Total: 29 testes — todos passando
