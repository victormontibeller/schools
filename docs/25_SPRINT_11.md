# Sprint 11 — Comunicação

## Objetivo

Implementar o sistema completo de comunicação da plataforma: notificações in-app, envio de e-mails e integração com WhatsApp, permitindo que a escola se comunique de forma eficiente com professores, alunos e responsáveis.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [x] Notificações in-app deverão ser exibidas em tempo real para o usuário logado.
- [x] E-mails deverão ser enviados de forma assíncrona via Celery.
- [x] WhatsApp deverá ser enviado de forma assíncrona via Celery (stub — `WhatsAppChannel` plugável).
- [x] Comunicados deverão poder ser enviados para: toda escola, turma específica, professores ou responsáveis.
- [x] Templates de mensagem deverão ser configuráveis por escola.
- [x] Toda mensagem enviada deverá ser registrada com status de entrega.
- [x] Toda operação deverá gerar auditoria e logs estruturados.

---

## Tarefas

### Módulo `notifications/`

- [x] Criar model `Notification` (Notificação In-App):
  - FK para `CustomUser` (destinatário)
  - `title`, `message`
  - `type` (info, alerta, crítico, sucesso)
  - `source` (módulo que gerou: `attendance`, `activities`, `calendar`, etc.)
  - `action_url` (link para a tela relacionada)
  - `read_at`
  - `correlation_id`
  - Herança de `BaseModel`

- [x] Criar model `Announcement` (Comunicado):
  - `title`, `body` (RichText)
  - `audience` (todos, professores, alunos, responsáveis, turma)
  - FK para `Class` (opcional)
  - `send_email`, `send_whatsapp` (flags)
  - `scheduled_at` (envio agendado)
  - `sent_at`
  - Herança de `BaseModel`

- [x] Criar model `MessageLog` (Registro de Envio):
  - FK para `Announcement`
  - FK para `CustomUser`
  - `channel` (email, whatsapp, in-app)
  - `status` (pendente, enviado, falhou)
  - `sent_at`, `error_message`
  - Herança de `BaseModel`

- [x] Criar model `MessageTemplate` (Template de Mensagem):
  - `name`, `subject`, `body`
  - `type` (boas-vindas, alerta de frequência, nova atividade, etc.)
  - `channel` (email, whatsapp)
  - Variáveis dinâmicas com sintaxe `{{ variavel }}`
  - Herança de `BaseModel`

- [x] Implementar `NotificationService`:
  - `create_notification(user_id, data)` — criação via evento interno
  - `mark_as_read(notification_id, user_id)`
  - `mark_all_as_read(user_id)`
  - `get_unread_count(user_id)`

- [x] Implementar `AnnouncementService`:
  - `create_announcement(data, created_by)` — envia imediatamente ou agenda
  - `send_announcement(announcement_id)` — dispara tasks Celery por canal
  - `get_audience_users(audience, class_id)` — retorna lista de destinatários

### SDK de Canais (`channels/`) — ADR-0005

- [x] Interface `BaseChannel` com método `send()` → `ChannelResult`
- [x] `EmailChannel` — SDK de e-mail via Django SMTP
- [x] `WhatsAppChannel` — stub plugável (Twilio/Z-API/Meta Cloud API)
- [x] `MessageTransport` — orquestrador genérico (render template + enviar + log + retry)

### Celery Tasks — E-mail

- [x] Task `send_email_task(user_id, template_id, context)`:
  - Renderizar template com variáveis dinâmicas
  - Enviar via `EmailChannel.send()`
  - `MessageLog` via `MessageTransport._log_result()`
  - Retry automático em caso de falha (máximo 3 tentativas)

- [x] Task `send_announcement_email_task(announcement_id)`:
  - Envio em lote via `MessageTransport.send_announcement_batch()`
  - Log individual por destinatário
  - Retry em caso de falha total

### Celery Tasks — WhatsApp

- [x] Task `send_whatsapp_task(phone, template_id, context)`:
  - Stub via `WhatsAppChannel.send()`
  - **Pendente: integrar provedor real (Twilio/Z-API/Meta)**
- [x] Task `send_announcement_whatsapp_task(announcement_id)`:
  - Stub para envio em lote via WhatsApp

### Handlers de Eventos Internos

- [x] Registrar handlers para eventos dos módulos anteriores:
  - `student.created` → notificação de boas-vindas ao responsável
  - `attendance.student_at_risk` → notificação de alerta ao responsável
  - `attendance.student_critical` → notificação crítica ao responsável + coordenador
  - `activity.created` → notificação de nova atividade ao aluno/responsável
  - `calendar.event_created` → notificação para audiência do evento (ALL via Celery, CLASS síncrono)

- [x] Helpers DRY: `_notify_guardians()` e `_notify_class_students()` eliminam duplicação entre handlers

### Frontend — Templates HTMX

- [x] Lista de notificações com HTMX polling (atualização a cada 30s)
- [x] Marcação individual e em lote como lida
- [x] Endpoint `/notifications/unread-count/` para contador
- [x] Tela de histórico de comunicados enviados

---

## Dependências

- Sprint 02 concluída: `CustomUser`
- Sprint 03 concluída: `Student`, `Guardian`
- Sprint 08 concluída: `Class`, `Activity`
- Sprint 09 concluída: `CalendarEvent`
- Sprint 10 concluída: `AttendanceRecord`

---

## Definition of Done

- [x] Todos os critérios de aceite validados
- [x] Testes de integração para envio de comunicado para múltiplos destinatários
- [x] `MessageLog` validado para todos os canais
- [x] Auditoria validada para comunicados enviados
- [x] Pipeline CI passando
- [x] SDK de canais documentado (ADR-0005)
- [ ] Provedor WhatsApp externo integrado (Twilio/Z-API/Meta) — **pendente de contrato**

---

## Progresso

> Atualizado em 2026-06-29

**Concluído:**
- 4 models: `Notification`, `Announcement`, `MessageLog`, `MessageTemplate`
- 2 services: `NotificationService`, `AnnouncementService` (com `validate_required`, `_deactivate` do `BaseService`)
- Channel SDK: `BaseChannel`, `EmailChannel`, `WhatsAppChannel` (ADR-0005)
- `MessageTransport`: orquestrador único de render + send + log + retry
- 5 Celery tasks (wrappers finos de ~10 linhas cada)
- Event handlers com helpers DRY (`_notify_guardians`, `_notify_class_students`)
- Templates HTMX: lista de notificações com polling, lista de comunicados
- 311 testes, cobertura 80.80%
- Ruff + Black passando

**Pendente:**
- Integração com provedor WhatsApp externo (Twilio/Z-API/Meta Cloud API)
- Mock de Celery nos testes de tasks (tasks testadas via channel mock)
- Sininho/drawer no header (requer atualização do `templates/base.html`)
- Formulários HTMX públicos para criação de comunicado e gestão de templates
