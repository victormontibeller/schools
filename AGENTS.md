# AGENTS.md — Guia para Agentes de IA

> Leia este arquivo **inteiro** antes de escrever qualquer código.
> Todas as regras aqui são obrigatórias e invioláveis.

---

## Leitura Obrigatória por Contexto

Antes de criar ou editar qualquer arquivo, leia o arquivo de instrução correspondente:

| Arquivo que vai criar/editar | Leia antes |
|---|---|
| `**/models.py` | `.github/instructions/models.instructions.md` |
| `**/services.py` | `.github/instructions/services.instructions.md` |
| `**/selectors.py` | `.github/instructions/selectors.instructions.md` |
| `**/views.py` | `.github/instructions/views.instructions.md` |
| `**/forms.py` | `.github/instructions/forms.instructions.md` |
| `**/templates/**/*.html` | `.github/instructions/templates.instructions.md` |
| `**/tests/**` ou `**/tests.py` | `.github/instructions/tests.instructions.md` |

Esses arquivos contêm padrões com exemplos de código reais do projeto. Não os ignore.

---

## 1. O que é este projeto

**School Manager** é uma plataforma **SaaS Multi-Tenant de Gestão Escolar** construída em:

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.13 + Django 5.1 |
| Banco de dados | PostgreSQL 15+ com isolamento por Schema (django-tenants) |
| Frontend | Django Templates + HTMX + Alpine.js + Bootstrap |
| Filas | Celery + RabbitMQ |
| Cache | Redis |
| Infra | Docker + Traefik + Prometheus + Loki + Grafana |

**Arquitetura:** Monólito Modular. Nunca proponha microserviços.

---

## 2. Regras Invioláveis

Antes de qualquer código, interiorize estas regras. Violá-las é proibido:

| Regra | Motivo |
|---|---|
| Regra de negócio **NUNCA** em views | Views orquestram; services decidem |
| Queries complexas **NUNCA** em views | Usar selectors |
| PII (email, CPF, telefone, nome) **NUNCA** em logs | `BaseService._log()` bloqueia automaticamente |
| Toda escrita **SEMPRE** gera auditoria | `BaseService._record_audit()` |
| `print()` para log é **PROIBIDO** | Usar `logging` com JSON estruturado |
| SQL direto é **PROIBIDO** | Usar ORM do Django |
| Nenhum registro pode ser **deletado fisicamente** | Soft delete obrigatório via `BaseModel` |
| Toda entidade **DEVE** herdar de `BaseModel` | UUID PK, timestamps, soft-delete, versioning |
| Secrets **NUNCA** em código | Variáveis de ambiente |
| Provedores externos (email, WhatsApp) **NUNCA** chamados diretamente em tasks | Usar `notifications/channels/` SDK |
| Todo contexto de Tenant **DEVE** ser respeitado | `django-tenants` roteia por Schema automaticamente |

---

## 3. Estrutura de Diretórios

```
base/           Python puro: BaseModel, BaseService, BaseSelector, exceções, eventos
core/           App Django principal: School (Tenant), CustomUser, Roles, Middleware
accounts/       Gestão de usuários, perfis, permissões
audit/          Registro de auditoria de todas as operações
teachers/       Professores e disciplinas
students/       Alunos
guardians/      Responsáveis de alunos
classes/        Turmas e matrículas
rooms/          Salas e recursos
agenda/         Grade horária
activities/     Atividades e avaliações
attendance/     Controle de frequência
academic_calendar/  Calendário acadêmico, eventos e feriados
notifications/  SDK de comunicação: Email, WhatsApp, transport
dashboard/      Dashboards escolar e executivo (KPIs, widgets, cache)
docs/           Toda a documentação do projeto
```

---

## 4. Camadas e Responsabilidades

```
Request HTTP
    └─▶ View (views.py)         — apenas orquestração: receber request → chamar service/selector → renderizar
          ├─▶ Service (services.py)   — toda regra de negócio, validação, auditoria, eventos
          ├─▶ Selector (selectors.py) — consultas read-only com paginação, nunca escreve
          └─▶ Form (forms.py)         — validação de campo apenas (required, tipo, choices)
```

### `models.py` — Schema apenas
```python
class Teacher(BaseModel):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    registration_number = models.CharField(max_length=20, unique=True)
    hire_date = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Teacher({self.user_id})"
```

### `services.py` — Regras de negócio
```python
class TeacherService(BaseService):
    def create_teacher(self, data: dict) -> Teacher:
        self.validate_required(data, ["user_id", "registration_number"])
        # ... validações de negócio ...
        teacher = Teacher.objects.create(
            created_by=self.user,
            updated_by=self.user,
            **clean_data,
        )
        self._record_audit("INSERT", teacher)
        self._log("teacher_created", teacher_id=str(teacher.id))
        return teacher

    def deactivate_teacher(self, teacher_id) -> Teacher:
        return self._deactivate(Teacher, teacher_id, "Teacher")
```

### `selectors.py` — Consultas read-only
```python
class TeacherSelector(BaseSelector):
    model_class = Teacher

    def list_active(self, page: int = 1) -> PageResult[Teacher]:
        return self.list(order_by="user__last_name", page=page)

    def get_by_user(self, user_id) -> Teacher:
        try:
            return Teacher.objects.select_related("user").get(user_id=user_id)
        except Teacher.DoesNotExist:
            raise ObjectNotFoundError("Teacher", str(user_id)) from None
```

### `views.py` — Orquestração HTTP apenas
```python
@login_required
def teacher_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = TeacherForm(request.POST)
        if form.is_valid():
            try:
                TeacherService(user=request.user).create_teacher(form.cleaned_data)
                messages.success(request, "Professor criado com sucesso.")
                return redirect("teachers:list")
            except ValidationError as exc:
                for field, errors in exc.errors.items():
                    form.add_error(field, errors)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        form = TeacherForm()
    return render(request, "teachers/create.html", {"form": form})
```

---

## 5. BaseService — Métodos Disponíveis

Nunca reimplemente o que já existe em `BaseService`:

| Método | Uso |
|---|---|
| `self.validate_required(data, ["field1", "field2"])` | Valida campos obrigatórios |
| `self._deactivate(ModelClass, entity_id, "Label")` | Soft-delete genérico com auditoria |
| `self._log("event_name", key=value)` | Log estruturado (bloqueia PII automaticamente) |
| `self._record_audit("INSERT"\|"UPDATE"\|"DELETE"\|"RESTORE", instance)` | Auditoria |

---

## 6. Exceções — Use Sempre as do `base/exceptions.py`

```python
from base.exceptions import ValidationError, ObjectNotFoundError, BusinessRuleViolationError

# Dados inválidos
raise ValidationError(errors={"field": ["Mensagem de erro."]})

# Registro não encontrado
raise ObjectNotFoundError("Teacher", str(teacher_id))

# Regra de negócio violada
raise BusinessRuleViolationError("Professor já está desativado.")
```

**Nunca** use `raise ValueError`, `raise Exception`, ou `raise Http404` em services.

---

## 7. BaseModel — Campos Disponíveis

Todo modelo herda automaticamente:
- `id` — UUID primary key
- `created_at`, `updated_at` — timestamps automáticos
- `created_by`, `updated_by` — FK para CustomUser (set manual no service)
- `is_active` — BooleanField (default True)
- `deleted_at`, `deleted_by` — soft delete
- `version` — controle otimista de concorrência
- `.objects` — Manager que filtra `is_active=True, deleted_at__isnull=True`
- `.all_objects` — Manager sem filtros

---

## 8. Logging — Regras de PII

```python
# CORRETO — IDs são OK
self._log("student_enrolled", student_id=str(student.id), class_id=str(class_id))

# ERRADO — PII em log é bloqueado automaticamente (levanta RuntimeError em DEBUG)
self._log("user_login", email=user.email)  # ← BLOQUEADO
```

Chaves **proibidas** em logs: `email`, `password`, `cpf`, `rg`, `phone`, `phone_whatsapp`,
`first_name`, `last_name`, `address`, `avatar`, ou qualquer chave que contenha "email" ou "password".

---

## 9. Multi-Tenant

O `django-tenants` ativa o schema correto automaticamente a partir do domínio da requisição.
Não há nada extra a fazer em views ou services para garantir isolamento.

**Tarefas Celery:** toda task deve receber o `tenant_schema_name` e ativar o schema:

```python
from django_tenants.utils import schema_context

@shared_task
def my_task(tenant_schema: str, student_id: str):
    with schema_context(tenant_schema):
        # ... lógica da task
```

---

## 10. Notificações — Use o SDK, nunca chame APIs externas diretamente

```python
# CORRETO
from notifications.transport import MessageTransport

MessageTransport().send(
    channel="email",
    recipient=user.email,  # email vai para transport; não aparece em logs de auditoria
    template="welcome",
    context={"name": user.first_name},
)

# ERRADO — chamada direta em task
import smtplib  # ← PROIBIDO em tasks ou services
```

---

## 11. Testes — Padrões Obrigatórios

- Framework: `pytest` + `pytest-django`
- Localização: `<app>/tests/` (subpasta) ou `<app>/tests.py`
- Nomenclatura: `test_<behavior>.py`, funções `test_<verbo>_<condition>()`
- Fixtures: `conftest.py` do app ou raiz

```python
import pytest
from base.exceptions import BusinessRuleViolationError, ValidationError

@pytest.mark.django_db
def test_create_teacher_fails_when_user_not_found(db_user):
    from teachers.services import TeacherService
    svc = TeacherService(user=db_user)
    with pytest.raises(ObjectNotFoundError):
        svc.create_teacher({"user_id": "00000000-0000-0000-0000-000000000000", "registration_number": "X"})
```

- Serviços devem ser testados isoladamente (mock de I/O quando necessário)
- Cobertura mínima: 80% (`fail_under = 80` no `pyproject.toml`)
- Testes de multi-tenant de isolamento: `make test-tenant`

---

## 12. Frontend — Templates Django

### Design System

O projeto usa o tema **Duralux** sobre Bootstrap 5. Classes de layout usam prefixo `nxl-*`.
Assets locais via `{% static %}`. HTMX via CDN.

```html
{# CSS — sempre estes 3, nesta ordem #}
<link rel="stylesheet" href="{% static 'css/bootstrap.min.css' %}">
<link rel="stylesheet" href="{% static 'css/vendors.min.css' %}">
<link rel="stylesheet" href="{% static 'css/theme.min.css' %}">
```

### Hierarquia de Herança Obrigatória

```
base.html                  ← toda tela usa este
  └── form_base.html       ← formulários herdam deste
        └── <app>/<resource>_form.html
  └── <app>/<resource>_list.html
        └── partials/<resource>_table.html   ← alvo dos updates HTMX
```

### Criando uma Tela de Listagem

```html
{% extends "base.html" %}
{% load static %}

{% block title %}Professores — School Manager{% endblock %}

{% block content %}
<div class="page-header">
    <div class="page-header-left d-flex align-items-center">
        <div class="page-header-title"><h5 class="m-b-10">Professores</h5></div>
        <ul class="breadcrumb">
            <li class="breadcrumb-item"><a href="{% url 'school_dashboard' %}">Home</a></li>
            <li class="breadcrumb-item active">Professores</li>
        </ul>
    </div>
    <div class="page-header-right ms-auto">
        <a href="{% url 'teacher_create' %}" class="btn btn-primary btn-sm">
            <i class="feather-plus me-1"></i> Novo
        </a>
    </div>
</div>

<div class="main-content">
    <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
            <h6 class="card-title mb-0">Lista de Professores</h6>
            {# Busca com debounce — atualiza apenas o #teachers-table #}
            <input type="text" name="q" value="{{ q|default:'' }}"
                   class="form-control form-control-sm w-auto"
                   placeholder="Buscar..."
                   hx-get="{% url 'teachers_list' %}"
                   hx-target="#teachers-table"
                   hx-trigger="keyup changed delay:300ms, search">
        </div>
        <div class="card-body p-0" id="teachers-table">
            {% include "teachers/partials/teachers_table.html" %}
        </div>
    </div>
</div>
{% endblock %}
```

### Partial de Tabela + Paginação

```html
{# teachers/partials/teachers_table.html #}
<table class="table table-hover mb-0">
    <thead class="table-light">
        <tr><th>Professor</th><th>Matrícula</th><th class="text-end">Ações</th></tr>
    </thead>
    <tbody>
        {% for teacher in result.items %}
        <tr>
            <td>{{ teacher.user.get_full_name }}</td>
            <td>{{ teacher.registration_number }}</td>
            <td class="text-end">
                <a href="{% url 'teacher_edit' teacher.pk %}" class="btn btn-sm btn-outline-secondary">
                    <i class="feather-edit-2"></i>
                </a>
            </td>
        </tr>
        {% empty %}
        <tr><td colspan="3" class="text-center text-muted py-4">Nenhum registro encontrado.</td></tr>
        {% endfor %}
    </tbody>
</table>

{# Paginação HTMX — preservar filtros na query string #}
{% if result.total_pages > 1 %}
<div class="d-flex justify-content-center py-3">
    <ul class="pagination pagination-sm mb-0">
        {% if result.has_previous %}
        <li class="page-item">
            <a class="page-link" hx-get="?page={{ result.page|add:'-1' }}{% if q %}&q={{ q }}{% endif %}"
               hx-target="#teachers-table" hx-swap="innerHTML">«</a>
        </li>
        {% endif %}
        <li class="page-item active"><span class="page-link">{{ result.page }} / {{ result.total_pages }}</span></li>
        {% if result.has_next %}
        <li class="page-item">
            <a class="page-link" hx-get="?page={{ result.page|add:'1' }}{% if q %}&q={{ q }}{% endif %}"
               hx-target="#teachers-table" hx-swap="innerHTML">»</a>
        </li>
        {% endif %}
    </ul>
</div>
{% endif %}
```

### Criando um Formulário

```html
{% extends "form_base.html" %}

{% block title %}{{ title }}{% endblock %}

{% block breadcrumb %}
<li class="breadcrumb-item"><a href="{% url 'teachers_list' %}">Professores</a></li>
{% endblock %}

{% block cancel_url %}{% url 'teachers_list' %}{% endblock %}
{# form_base.html já fornece: CSRF, iteração de campos, botões Salvar + Cancelar #}
{# Para upload: {% block form_enctype %}enctype="multipart/form-data"{% endblock %} #}
```

### Padrões HTMX

| Caso de uso | Padrão |
|---|---|
| Busca com debounce | `hx-trigger="keyup changed delay:300ms, search"` |
| Paginação | `hx-get="?page=N&q={{ q }}" hx-target="#container" hx-swap="innerHTML"` |
| Submit sem reload | `hx-post="..." hx-target="#result" hx-swap="innerHTML"` |
| Auto-refresh | `hx-trigger="every 60s" hx-swap="outerHTML"` |
| Lazy load | `hx-trigger="load" hx-target="#container" hx-swap="innerHTML"` |

### Mensagens de Feedback

```python
# Na view — base.html exibe automaticamente
messages.success(request, "Salvo com sucesso.")   # → alert-success
messages.error(request, exc.message)              # → alert-danger
```

### Ícones (Feather Icons)

```html
<i class="feather-plus"></i>    <i class="feather-edit-2"></i>   <i class="feather-trash-2"></i>
<i class="feather-eye"></i>     <i class="feather-search"></i>   <i class="feather-calendar"></i>
```

### Regras de Frontend

- **Nunca** Bootstrap via CDN — usar `{% static 'css/bootstrap.min.css' %}`
- **Nunca** `{% csrf_token %}` omitido em `<form method="post">`
- **Sempre** `{% extends "base.html" %}` ou `{% extends "form_base.html" %}`
- **Sempre** `{% block title %}` preenchido
- **Sempre** `{% empty %}` em tabelas para estado vazio
- **Sempre** paginação preserva query string (`q`, filtros)
- **Sem JS complexo** — usar HTMX

---

## 13. Criando um Novo Módulo

Checklist para cada novo app Django:

- [ ] `models.py` — herdar de `BaseModel`
- [ ] `services.py` — herdar de `BaseService`
- [ ] `selectors.py` — herdar de `BaseSelector`
- [ ] `views.py` — somente orquestração HTTP
- [ ] `forms.py` — somente validação de campo
- [ ] `urls.py` — prefixo `/nome-do-modulo/`
- [ ] `admin.py` — registrar models
- [ ] `apps.py` — configurar `AppConfig`
- [ ] `migrations/` — pasta de migrations
- [ ] `tests/` — pasta de testes
- [ ] `templates/<app>/` — templates HTML
- [ ] Registrar em `INSTALLED_APPS` no `core/settings.py`
- [ ] Incluir URLs em `core/urls.py`
- [ ] Adicionar app à cobertura em `pyproject.toml [tool.coverage.run]`
- [ ] Logs: toda operação de escrita deve ter `self._log()`
- [ ] Auditoria: toda escrita deve ter `self._record_audit()`

---

## 14. Definition of Done

Um item só pode ser considerado concluído quando:

- [ ] Código funcional
- [ ] `ruff check .` sem erros
- [ ] `black --check .` sem erros
- [ ] Migration criada e revisada
- [ ] Logs implementados em todas as operações do service
- [ ] Auditoria implementada em todas as escritas
- [ ] Testes escritos e passando (`pytest` verde)
- [ ] Documentação atualizada se decisão arquitetural

---

## 15. O que NUNCA Fazer

```python
# ❌ Regra de negócio em view
def student_create(request):
    if Student.objects.filter(registration=data["reg"]).exists():  # ← mover para service
        ...

# ❌ Query na view
def class_list(request):
    classes = Class.objects.filter(is_active=True).order_by("name")  # ← usar selector

# ❌ PII em log
logger.info("Login", extra={"email": user.email})  # ← bloqueado pelo BaseService

# ❌ print() para debug
print(f"Debug: {student}")  # ← proibido; usar logging

# ❌ Exceção genérica em service
raise ValueError("Erro")  # ← usar base.exceptions

# ❌ SQL direto
from django.db import connection
cursor.execute("SELECT * FROM students")  # ← usar ORM

# ❌ Segredo em código
OPENAI_API_KEY = "sk-..."  # ← variável de ambiente obrigatória

# ❌ Deletar registro fisicamente
student.delete()  # ← usar student.soft_delete(user=request.user)
```

---

## 16. Documentação de Referência

| Documento | Conteúdo |
|---|---|
| `docs/00_PROJECT_VISION.md` | Missão, princípios e stack |
| `docs/02_ARCHITECTURE.md` | Arquitetura, fluxo de requisição |
| `docs/03_ENGINEERING_RULES.md` | Regras obrigatórias e proibições |
| `docs/04_SECURITY.md` | OWASP, CSRF, PII, rate limiting |
| `docs/05_DATABASE.md` | BaseModel, soft-delete, migrations |
| `docs/06_MULTI_TENANT.md` | django-tenants, Schema isolation |
| `docs/09_UI_GUIDELINES.md` | Padrões de frontend |
| `docs/10_CODING_STANDARDS.md` | DRY, camadas, catálogo de helpers |
| `docs/12_DEFINITION_OF_DONE.md` | Critérios de aceite |
| `docs/adr/` | Architecture Decision Records |
| `.github/instructions/models.instructions.md` | Padrões de models com exemplos |
| `.github/instructions/services.instructions.md` | Padrões de services com exemplos |
| `.github/instructions/selectors.instructions.md` | Padrões de selectors com exemplos |
| `.github/instructions/views.instructions.md` | Padrões de views com exemplos |
| `.github/instructions/forms.instructions.md` | Padrões de forms e widgets |
| `.github/instructions/templates.instructions.md` | Padrões de templates, HTMX, Bootstrap |
| `.github/instructions/tests.instructions.md` | Padrões de testes com exemplos |
| `docs/10_CODING_STANDARDS.md` | DRY, camadas, catálogo de helpers |
| `docs/12_DEFINITION_OF_DONE.md` | Critérios de aceite |
| `docs/adr/` | Architecture Decision Records |
