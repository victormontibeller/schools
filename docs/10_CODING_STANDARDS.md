# Coding Standards

> **Escopo:** convenções de código e catálogo de helpers. As regras normativas de arquitetura, segurança e entrega estão, respectivamente, em `docs/03_ENGINEERING_RULES.md`, `docs/04_SECURITY.md` e `docs/12_DEFINITION_OF_DONE.md`.

## Ferramentas

- **PEP8** — style guide base
- **Black** — formatação automática (line-length = 100)
- **Ruff** — linting + import sorting
- **Type Hints** — obrigatórios em toda função/método público
- **Docstrings** — obrigatórias em todo módulo, classe e função pública

## Princípios

- **Clean Code** — nomes significativos, funções pequenas, uma responsabilidade por classe
- **KISS** — soluções simples primeiro; complexidade só quando justificada
- **YAGNI** — não implementar funcionalidades antes da necessidade real
- **DRY** — zero duplicação; extrair para `base/` ou helpers reutilizáveis

## DRY — Catálogo de Rotinas Genéricas

O projeto mantém helpers no `BaseService` e `BaseSelector` para eliminar repetição:

### Em `base/services.py` (BaseService)

| Método | Substitui | Uso |
|--------|-----------|-----|
| `validate_required(data, fields)` | Bloco `required = [...]` + `for/if/raise` | `self.validate_required(data, ["name", "email"])` |
| `_deactivate(model, id, label)` | 13 linhas de try/except/soft_delete | `self._deactivate(Teacher, tid, "Teacher")` |

### Em `base/exceptions.py`

| Exceção | Quando usar |
|---------|------------|
| `ValidationError(errors=dict)` | Dados inválidos (campos obrigatórios, formato, unicidade) |
| `ObjectNotFoundError(model, id)` | Entidade não encontrada |
| `BusinessRuleViolationError(msg)` | Regra de domínio violada (ex: já desativado, sem vagas) |

### Em `notifications/` (SDK de Comunicação)

| Componente | Propósito |
|-----------|-----------|
| `channels/BaseChannel` | Interface que todo provedor externo implementa |
| `channels/EmailChannel` | SDK de e-mail via Django SMTP |
| `channels/WhatsAppChannel` | SDK de WhatsApp (stub — plugar Twilio/Z-API) |
| `transport/MessageTransport` | Orquestrador: render template + enviar + log + retry |

Para adicionar um novo provedor de WhatsApp:
```python
# notifications/channels/whatsapp.py
class WhatsAppChannel(BaseChannel):
    channel_name = "WHATSAPP"

    def send(self, recipient_address, subject, body, **meta):
        from twilio.rest import Client
        client = Client(settings.TWILIO_SID, settings.TWILIO_TOKEN)
        client.messages.create(body=body, to=recipient_address, ...)
        return ChannelResult(success=True, ...)
```
**Zero alterações em tasks, transport ou handlers.**

## Camadas e Responsabilidades

| Camada | Responsabilidade | Exemplo |
|--------|-----------------|---------|
| `models.py` | Schema, campos, índices, `__str__` | `Class(BaseModel)`, `Enrollment(BaseModel)` |
| `services.py` | Regras de negócio, validação, auditoria | `ClassService.enroll_student()`, `validate_required()` |
| `selectors.py` | Consultas read-only, paginação, agregação | `ClassSelector.list_ordered()`, `get_month_grid()` |
| `views.py` | Orquestração HTTP (receber request → chamar service/selector → renderizar) | `class_create(request)` |
| `forms.py` | Validação de formulário (apenas field-level: required, tipo, choices) | `ClassForm(forms.ModelForm)` |
| `tasks.py` | Operações assíncronas (Celery wrappers finos) | `send_email_task.delay(user_id, template_id, ctx)` |
| `handlers.py` | Eventos cross-module (DomainEvent → notificação) | `_handle_student_created(event)` |

## Regras Invioláveis

- **Regra de negócio = `services.py`**. Nunca em views, forms ou templates.
- **Query complexa = `selectors.py`**. Nunca `Model.objects.filter()` direto na view.
- **Provedor externo = `channels/` SDK**. Nunca chamada direta a API de terceiro em task.
- **PII nunca em logs** — `BaseService._log()` bloqueia email, phone, cpf, etc.
- **Toda escrita gera auditoria** — `BaseService._record_audit()`.
- **Nenhum segredo em código** — credenciais via `School.settings` (tenant) ou variáveis de ambiente.
