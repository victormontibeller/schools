---
applyTo: "**/templates/**/*.html"
---

# Frontend — Padrões Obrigatórios

## Design System: Duralux (Bootstrap 5)

O projeto usa o tema **Duralux** sobre Bootstrap 5. Classes de layout são prefixadas com `nxl-*`.
Assets são carregados via `{% static %}` (nunca CDN para Bootstrap/tema). HTMX via CDN.

```html
{# CSS — sempre estes 3, nesta ordem #}
<link rel="stylesheet" href="{% static 'css/bootstrap.min.css' %}">
<link rel="stylesheet" href="{% static 'css/vendors.min.css' %}">
<link rel="stylesheet" href="{% static 'css/theme.min.css' %}">

{# JS — sempre estes 3 + HTMX, antes do </body> #}
<script src="{% static 'js/vendors.min.js' %}"></script>
<script src="{% static 'js/common-init.min.js' %}"></script>
<script src="https://unpkg.com/htmx.org@1.9.12"></script>
```

---

## Hierarquia de Templates

```
base.html                          ← layout raiz (nav, header, messages, blocks)
  └── form_base.html               ← base para formulários (card com form)
        └── <app>/templates/<app>/<resource>_form.html
  └── <app>/templates/<app>/<resource>_list.html
  └── <app>/templates/<app>/<resource>_detail.html
        └── partials/<resource>_table.html   ← tabela + paginação (alvo HTMX)
```

**Blocks disponíveis em `base.html`:**
- `{% block title %}` — título da página
- `{% block content %}` — conteúdo principal
- `{% block extra_css %}` — CSS específico da página
- `{% block extra_js %}` — JS específico da página

---

## Perfil de Pessoa — Agrupamento Obrigatório

Telas de detalhe de pessoas (`Teacher`, `Student`, `Guardian` e futuras entidades pessoais)
devem agrupar identidade, dados pessoais, documentos e contato em **um único card**:

```
row g-3
├── col-xl-5: Informações da Pessoa
│   ├── avatar + nome + identificador principal
│   └── dl com nascimento, gênero, documentos e contatos
└── col-xl-7: relações do domínio
    ├── card de disciplinas/responsáveis/alunos vinculados
    └── card de endereços
```

Regras:

- **Nunca** separar “Dados Pessoais”, “Documentos” e “Contato” em cards diferentes.
- Endereços ficam sempre em card próprio, usando `addresses/partials/address_table.html`.
- Relações relevantes ficam em card próprio: disciplinas, responsáveis ou alunos vinculados.
- Campos sem valor devem aparecer como `—`, evitando saltos e layouts diferentes por cadastro.
- Quando a edição for inline com HTMX, a ação “Editar” fica no cabeçalho do próprio card e
  substitui somente esse componente; em telas com formulário dedicado, fica no `page-header-right`.
- Relações do domínio, como disciplinas, são gerenciadas no próprio card e nunca misturadas
  ao formulário de informações pessoais.
- Usar `row g-3 align-items-start`, `col-12 col-xl-5` e `col-12 col-xl-7`.
- Em telas pequenas, os cards devem empilhar sem overflow horizontal.

---

## Contrato de Tabelas de Listagem

- Botões de cadastro exibem somente o ícone de adição e a legenda `NOVO`, sem repetir o domínio.
- A primeira coluna identifica o registro e é sempre o link principal da linha.
- Para entidades com tela de detalhe ou perfil, a primeira coluna aponta para essa tela.
- Sem tela de detalhe, usar a tela operacional principal (edição, chamada ou lançamento).
- Evitar coluna “Ações” contendo apenas “Ver” ou “Editar”; mantê-la somente para ações adicionais.
- Envolver toda tabela com `<div class="table-responsive">`.
- Usar `table table-hover mb-0` e paginação HTMX centralizada.
- Preservar todos os filtros na paginação.

---

## Criando uma Tela de Listagem

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
            <i class="feather-plus me-1"></i> Novo Professor
        </a>
    </div>
</div>

<div class="main-content">
    <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
            <h6 class="card-title mb-0">Lista de Professores</h6>
            {# Busca com debounce — atualiza apenas o #teachers-table #}
            <form class="d-flex gap-2"
                  hx-get="{% url 'teachers_list' %}"
                  hx-target="#teachers-table"
                  hx-trigger="submit">
                <input type="text" name="q" value="{{ q|default:'' }}"
                       class="form-control form-control-sm"
                       placeholder="Buscar..."
                       hx-get="{% url 'teachers_list' %}"
                       hx-target="#teachers-table"
                       hx-trigger="keyup changed delay:300ms, search">
                <button class="btn btn-sm btn-outline-secondary">Buscar</button>
            </form>
        </div>
        <div class="card-body p-0" id="teachers-table">
            {% include "teachers/partials/teachers_table.html" %}
        </div>
    </div>
</div>
{% endblock %}
```

### Partial de tabela (`partials/<resource>_table.html`)

```html
{# teachers/templates/teachers/partials/teachers_table.html #}
<table class="table table-hover mb-0">
    <thead class="table-light">
        <tr>
            <th>Professor</th>
            <th>Matrícula</th>
            <th>Status</th>
            <th class="text-end">Ações</th>
        </tr>
    </thead>
    <tbody>
        {% for teacher in result.items %}
        <tr>
            <td>
                <a href="{% url 'teacher_detail' teacher.pk %}" class="fw-semibold">
                    {{ teacher.user.get_full_name }}
                </a>
            </td>
            <td>{{ teacher.registration_number }}</td>
            <td>
                {% if teacher.is_active %}
                    <span class="badge bg-success">Ativo</span>
                {% else %}
                    <span class="badge bg-secondary">Inativo</span>
                {% endif %}
            </td>
            <td class="text-end">
                <a href="{% url 'teacher_detail' teacher.pk %}" class="btn btn-sm btn-outline-primary">
                    <i class="feather-eye"></i>
                </a>
                <a href="{% url 'teacher_edit' teacher.pk %}" class="btn btn-sm btn-outline-secondary">
                    <i class="feather-edit-2"></i>
                </a>
            </td>
        </tr>
        {% empty %}
        <tr>
            <td colspan="4" class="text-center text-muted py-4">Nenhum professor encontrado.</td>
        </tr>
        {% endfor %}
    </tbody>
</table>

{# Paginação HTMX — padrão do projeto #}
{% if result.total_pages > 1 %}
<div class="d-flex justify-content-center py-3">
    <nav>
        <ul class="pagination pagination-sm mb-0">
            {% if result.has_previous %}
            <li class="page-item">
                <a class="page-link"
                   hx-get="?page={{ result.page|add:'-1' }}{% if q %}&q={{ q }}{% endif %}"
                   hx-target="#teachers-table"
                   hx-swap="innerHTML">«</a>
            </li>
            {% endif %}
            <li class="page-item active">
                <span class="page-link">{{ result.page }} / {{ result.total_pages }}</span>
            </li>
            {% if result.has_next %}
            <li class="page-item">
                <a class="page-link"
                   hx-get="?page={{ result.page|add:'1' }}{% if q %}&q={{ q }}{% endif %}"
                   hx-target="#teachers-table"
                   hx-swap="innerHTML">»</a>
            </li>
            {% endif %}
        </ul>
    </nav>
</div>
{% endif %}
```

---

## Criando um Formulário

Sempre herdar de `form_base.html`. Não reinventar o layout de card + form.

```html
{% extends "form_base.html" %}

{% block title %}{{ title }}{% endblock %}

{% block breadcrumb %}
<li class="breadcrumb-item"><a href="{% url 'teachers_list' %}">Professores</a></li>
{% endblock %}

{% block cancel_url %}{% url 'teachers_list' %}{% endblock %}
{# submit_label e form_enctype têm defaults OK para maioria dos casos #}
```

**`form_base.html` já fornece:**
- Layout de card com header e body
- `{% csrf_token %}` automático
- Iteração de campos via `{% include "partials/form_field.html" %}`
- Erros non_field_errors
- Botões Salvar + Cancelar

**Para upload de arquivo,** adicionar:
```html
{% block form_enctype %}enctype="multipart/form-data"{% endblock %}
```

---

## Renderização de Campos — `partials/form_field.html`

O partial `partials/form_field.html` renderiza qualquer campo automaticamente:
- Checkboxes → `form-check form-switch`
- Textarea / SelectMultiple → col-12 (largura total)
- Demais campos → col-lg-6 (2 colunas em desktop)
- Erros → `text-danger small`
- Campos obrigatórios → asterisco vermelho `<span class="text-danger">*</span>`

**Nunca** renderize campos manualmente quando `form_base.html` funcionar.
Para layouts customizados com campos específicos:

```html
{% block content %}
{# ... card wrapper ... #}
<form method="post">
    {% csrf_token %}
    <div class="row g-3">
        <div class="col-12">
            {% include "partials/form_field.html" with field=form.title %}
        </div>
        <div class="col-lg-6">
            {% include "partials/form_field.html" with field=form.start_date %}
        </div>
        <div class="col-lg-6">
            {% include "partials/form_field.html" with field=form.end_date %}
        </div>
    </div>
    <button type="submit" class="btn btn-primary mt-3">Salvar</button>
</form>
{% endblock %}
```

---

## Padrões HTMX

| Caso de uso | Padrão |
|---|---|
| Busca com debounce | `hx-trigger="keyup changed delay:300ms, search"` |
| Submit de form | `hx-post="..." hx-target="#result" hx-swap="innerHTML"` |
| Paginação | `hx-get="?page=N&q={{ q }}" hx-target="#container" hx-swap="innerHTML"` |
| Auto-refresh | `hx-trigger="every 60s" hx-swap="outerHTML"` |
| Carregar ao abrir | `hx-trigger="load" hx-target="#container" hx-swap="innerHTML"` |
| Navegar sem reload | `hx-get="..." hx-target="#container" hx-push-url="true"` |
| Editar card inline | `hx-get=".../editar/" hx-target="#card-id" hx-swap="outerHTML"` |

**Sempre** preserve query params (`q`, filtros) nos links de paginação.

### Confirmação de ação destrutiva

Use `hx-confirm` — exibe `window.confirm()` nativo antes de disparar a request:

```html
<button type="button"
        hx-post="{% url 'teacher_deactivate' teacher.pk %}"
        hx-confirm="Desativar {{ teacher.user.get_full_name }}?"
        hx-target="#teachers-table"
        hx-swap="innerHTML"
        class="btn btn-sm btn-outline-danger"
        aria-label="Desativar professor">
    <i class="feather-trash-2"></i>
</button>
```

### Indicador de carregamento

```html
{# htmx-indicator: visível apenas durante requests HTMX #}
<button hx-post="..." hx-indicator="#spin-salvar" class="btn btn-primary">
    Salvar
    <span id="spin-salvar"
          class="htmx-indicator spinner-border spinner-border-sm ms-1"
          role="status"
          aria-label="Carregando..."></span>
</button>
```

### Collapse Bootstrap (seções expansíveis)

```html
<button class="btn btn-outline-secondary btn-sm"
        type="button"
        data-bs-toggle="collapse"
        data-bs-target="#extra-section">
    <i class="feather-chevron-down me-1"></i> Ver detalhes
</button>
<div class="collapse mt-3" id="extra-section">
    {# conteúdo expansível — ex: formulário de cancelamento, notas extras #}
</div>
```

---

## Acessibilidade

- Botões com **apenas ícone** devem ter `aria-label`:
```html
{# ❌ inacessível #}
<button class="btn btn-sm btn-outline-secondary"><i class="feather-edit-2"></i></button>

{# ✅ correto #}
<button class="btn btn-sm btn-outline-secondary" aria-label="Editar professor">
    <i class="feather-edit-2"></i>
</button>
```
- Links de paginação: `aria-label="Página anterior"` / `aria-label="Próxima página"`
- Imagens: `alt=""` para decorativas; `alt="Descrição"` para conteúdo

---

## Mensagens (Feedback ao Usuário)

`base.html` já exibe `messages` automaticamente. Nunca re-implementar.

```python
# Na view — isso já aparece na próxima página via base.html
messages.success(request, "Professor criado com sucesso.")
messages.error(request, exc.message)
messages.warning(request, "Atenção: dados incompletos.")
```

Tags mapeadas para Bootstrap:
- `messages.success` → `alert-success` (verde)
- `messages.error` → `alert-danger` (vermelho)
- `messages.warning` → `alert-warning` (amarelo)
- `messages.info` → `alert-info` (azul)

---

## Template Tags Disponíveis

```python
# widget_utils (core) — detectar tipo de widget
{% load widget_utils %}
{% with wt=field.field.widget|widget_type %}  {# ex: "TextareaInput", "Select" #}

# calendar_extras (academic_calendar) — acessar dict em template
{% load calendar_extras %}
{% for ev in by_day|get:day %}

# dashboard_extras (dashboard) — valor padrão
{% load dashboard_extras %}
{{ value|default:"—" }}
```

---

## Ícones

O projeto usa **Feather Icons** (incluído no `vendors.min.css`):

```html
<i class="feather-plus"></i>        <!-- + -->
<i class="feather-edit-2"></i>      <!-- lápis -->
<i class="feather-trash-2"></i>     <!-- lixeira -->
<i class="feather-eye"></i>         <!-- olho -->
<i class="feather-search"></i>      <!-- lupa -->
<i class="feather-user"></i>        <!-- usuário -->
<i class="feather-users"></i>       <!-- usuários -->
<i class="feather-calendar"></i>    <!-- calendário -->
<i class="feather-check"></i>       <!-- check -->
<i class="feather-x"></i>           <!-- x / fechar -->
```

---

## Regras

- **Nunca** bootstrap CDN — usar `{% static 'css/bootstrap.min.css' %}`
- **Nunca** JavaScript customizado complexo — usar HTMX
- **Nunca** `{% load static %}` esquecido quando usar `{% static %}`
- **Nunca** `{% csrf_token %}` omitido em `<form method="post">`
- **Sempre** `{% extends "base.html" %}` ou `{% extends "form_base.html" %}`
- **Sempre** `{% block title %}` preenchido com nome da tela
- **Sempre** breadcrumb na listagem e formulário
- **Sempre** `{% empty %}` em loops de tabela para estado vazio
- HTMX alvo deve ser o **container mínimo** necessário (não a página inteira)
- Paginação preserva filtros de busca na query string
