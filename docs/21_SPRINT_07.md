# Sprint 07 — Comunicação

## Objetivo

Implementar o sistema completo de comunicação da plataforma: notificações in-app, envio de e-mails e integração com WhatsApp, permitindo que a escola se comunique de forma eficiente com professores, alunos e responsáveis.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [ ] Notificações in-app deverão ser exibidas em tempo real para o usuário logado.
- [ ] E-mails deverão ser enviados de forma assíncrona via Celery.
- [ ] WhatsApp deverá ser enviado de forma assíncrona via Celery.
- [ ] Comunicados deverão poder ser enviados para: toda escola, turma específica, professores ou responsáveis.
- [ ] Templates de mensagem deverão ser configuráveis por escola.
- [ ] Toda mensagem enviada deverá ser registrada com status de entrega.
- [ ] Toda operação deverá gerar auditoria e logs estruturados.

---

## Tarefas

### Módulo `notifications/`

- [ ] Criar model `Notification` (Notificação In-App):
  - FK para `CustomUser` (destinatário)
  - `title`, `message`
  - `type` (info, alerta, crítico, sucesso)
  - `source` (módulo que gerou: `attendance`, `activities`, `calendar`, etc.)
  - `action_url` (link para a tela relacionada)
  - `read_at`
  - `correlation_id`
  - Herança de `BaseModel`

- [ ] Criar model `Announcement` (Comunicado):
  - `title`, `body` (RichText)
  - `audience` (todos, professores, alunos, responsáveis, turma)
  - FK para `Class` (opcional)
  - `send_email`, `send_whatsapp` (flags)
  - `scheduled_at` (envio agendado)
  - `sent_at`
  - Herança de `BaseModel`

- [ ] Criar model `MessageLog` (Registro de Envio):
  - FK para `Announcement`
  - FK para `CustomUser`
  - `channel` (email, whatsapp, in-app)
  - `status` (pendente, enviado, falhou)
  - `sent_at`, `error_message`
  - Herança de `BaseModel`

- [ ] Criar model `MessageTemplate` (Template de Mensagem):
  - `name`, `subject`, `body`
  - `type` (boas-vindas, alerta de frequência, nova atividade, etc.)
  - `channel` (email, whatsapp)
  - Variáveis dinâmicas com sintaxe `{{ variavel }}`
  - Herança de `BaseModel`

- [ ] Implementar `NotificationService`:
  - `create_notification(user_id, data)` — criação via evento interno
  - `mark_as_read(notification_id, user_id)`
  - `mark_all_as_read(user_id)`
  - `get_unread_count(user_id)`

- [ ] Implementar `AnnouncementService`:
  - `create_announcement(data, created_by)` — envia imediatamente ou agenda
  - `send_announcement(announcement_id)` — dispara tasks Celery por canal
  - `get_audience_users(audience, class_id)` — retorna lista de destinatários

### Celery Tasks — E-mail

- [ ] Task `send_email_task(user_id, template_id, context)`:
  - Renderizar template com variáveis dinâmicas
  - Enviar via SMTP configurado
  - Atualizar `MessageLog` com status
  - Retry automático em caso de falha (máximo 3 tentativas)

### Celery Tasks — WhatsApp

- [ ] Task `send_whatsapp_task(phone, template_id, context)`:
  - Integrar com provedor WhatsApp (Twilio, Z-API ou Meta Cloud API)
  - Configuração do provedor via settings do Tenant
  - Atualizar `MessageLog` com status
  - Retry automático em caso de falha

### Frontend — Templates HTMX

- [ ] Sininho de notificações no header com contador de não lidas (atualização via HTMX polling)
- [ ] Painel de notificações deslizante (drawer) com lista e marcação como lida
- [ ] Formulário de criação de comunicado com seleção de audiência e canais
- [ ] Tela de histórico de comunicados enviados com status por canal
- [ ] Tela de gestão de templates de mensagem

### Handlers de Eventos Internos

- [ ] Registrar handlers para eventos dos módulos anteriores:
  - `student.created` → notificação de boas-vindas ao responsável
  - `attendance.student_at_risk` → notificação de alerta ao responsável
  - `attendance.student_critical` → notificação crítica ao responsável + coordenador
  - `activity.created` → notificação de nova atividade ao aluno/responsável
  - `calendar.event_created` → notificação para audiência do evento

---

## Dependências

- Sprint 02 concluída: `CustomUser`
- Sprint 03 concluída: `Student`, `Guardian`
- Sprint 04 concluída: `Class`, `Activity`
- Sprint 05 concluída: `CalendarEvent`
- Sprint 06 concluída: `AttendanceRecord`

---

## Definition of Done

- [ ] Todos os critérios de aceite validados
- [ ] Tasks Celery com retry testadas com mock do provedor de e-mail
- [ ] Testes de integração para envio de comunicado para múltiplos destinatários
- [ ] `MessageLog` validado para todos os canais
- [ ] Auditoria validada para comunicados enviados
- [ ] Pipeline CI passando
