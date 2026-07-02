# UI Guidelines

## Stack

| Tecnologia | Uso |
|---|---|
| **Duralux** | Tema principal sobre Bootstrap 5 — classes `nxl-*` para shell, nav e layout |
| **Bootstrap 5** | Grid, componentes (cards, modais, badges, alertas, paginação, tabelas) |
| **HTMX 1.9** | Interatividade sem JS: busca, paginação, submit, polling, carregamento lazy |
| **Feather Icons** | Ícones (`<i class="feather-*">`) — incluído no `vendors.min.css` |
| **Alpine.js** | Disponível mas **não em uso** — Bootstrap JS cobre dropdowns e modais |

---

## Princípios

- **Server-side rendering first:** toda renderização inicial é feita pelo Django Templates.
- **HTMX para atualizações parciais:** recarregar apenas o fragmento relevante, não a página inteira.
- **Sem JS customizado complexo:** se precisar de mais de ~10 linhas de JS, rever o design.
- **Herança obrigatória:** toda tela usa `{% extends "base.html" %}` ou `{% extends "form_base.html" %}`.

---

## Hierarquia de Templates

```
templates/
    base.html          — layout raiz (nav sidebar, header, messages, blocks)
    form_base.html     — base para formulários (card + form + botões)
    partials/
        form_field.html — renderização automática de campo Django

<app>/templates/<app>/
    <resource>_list.html    — listagem com busca + HTMX
    <resource>_form.html    — formulário (herda form_base.html)
    <resource>_detail.html  — visualização detalhada
    partials/
        <resource>_table.html  — tabela + paginação (alvo HTMX)
```

---

## Perfil de Pessoa

Perfis de professor, aluno, responsável e futuras entidades pessoais seguem uma estrutura única:

- Um card **Informações da Pessoa** reúne avatar, nome, identificador, dados pessoais,
  documentos e contato.
- Um card separado apresenta relações do domínio, como disciplinas, responsáveis ou alunos.
- Endereços ficam em card próprio por meio de `addresses/partials/address_table.html`.
- Dados pessoais, documentos e contato nunca devem ser fragmentados em cards diferentes.
- Valores ausentes são exibidos como `—`.
- Edições inline ficam no cabeçalho do próprio card e substituem somente aquele componente.
- Relações como disciplinas são vinculadas no card próprio, separadas dos dados pessoais.
- Layout desktop: `col-xl-5` para a pessoa e `col-xl-7` para relações/endereço.
- Layout mobile: cards empilhados, sem overflow horizontal.

Usuários administrativos seguem o mesmo agrupamento: identidade, contato, perfil de acesso,
status e data de ingresso ficam em um único card. A listagem abre essa ficha, não uma edição.

## Perfil da Empresa

- A rota principal de Empresa exibe primeiro a ficha institucional.
- Nome, documentos, contato institucional e responsável ficam no card
  **Informações da Empresa**.
- Endereços permanecem em card separado.
- O formulário é acessado pelo botão **Editar** no cabeçalho da ficha.

---

## Padrões de HTMX

```html
{# Busca com debounce #}
<input hx-get="{% url 'list' %}"
       hx-target="#container"
       hx-trigger="keyup changed delay:300ms, search"
       name="q">

{# Paginação — sempre preservar filtros #}
<a hx-get="?page={{ result.page|add:'1' }}&q={{ q }}"
   hx-target="#container"
   hx-swap="innerHTML">»</a>

{# Submit sem reload #}
<form hx-post="{% url 'create' %}"
      hx-target="#result"
      hx-swap="innerHTML">

{# Auto-refresh #}
<div hx-get="{% url 'partial' %}"
     hx-trigger="every 60s"
     hx-swap="outerHTML">

{# Carregar ao exibir #}
<div hx-get="{% url 'partial' %}"
     hx-trigger="load"
     hx-target="#container"
     hx-swap="innerHTML">
```

---

## Tabelas de Listagem

- A primeira coluna é a identificação e o link principal do registro.
- Para pessoas e demais entidades com tela de detalhe, o link aponta para a ficha completa.
- Sem tela de detalhe, o link aponta para a tela operacional principal, como edição ou lançamento.
- Coluna de ações não deve existir apenas para repetir “Ver” ou “Editar”.
- Ações secundárias, como desativar, permanecem na última coluna.
- Todas as tabelas usam `table-responsive`, `table table-hover mb-0` e paginação HTMX uniforme.
- Busca, contador, botão de criação e card seguem `partials/list_header.html`.

---

## Cabeçalho da Aplicação

- Notificações usam botão compacto com foco/hover e contador oculto quando zerado.
- O usuário usa um controle com avatar, nome, perfil e indicador do menu.
- Em telas pequenas, textos secundários são ocultados sem reduzir a área clicável.

---

## Formulários

- Herdar de `form_base.html` — fornece card, CSRF, iteração de campos, botões.
- Campos renderizados via `{% include "partials/form_field.html" with field=field %}`.
- Erros de campo: `text-danger small` (automático via partial).
- Erros do service: `messages.error(request, exc.message)` — aparece no `base.html`.
- Upload de arquivo: `{% block form_enctype %}enctype="multipart/form-data"{% endblock %}`.

---

## Mensagens

Django messages são exibidas automaticamente em `base.html`. Nunca re-implementar.

```python
messages.success(request, "Salvo com sucesso.")   # → alert-success
messages.error(request, exc.message)              # → alert-danger
messages.warning(request, "Atenção: ...")         # → alert-warning
messages.info(request, "Informação: ...")         # → alert-info
```

---

## Ícones Feather (mais usados)

```html
<i class="feather-plus"></i>      <i class="feather-edit-2"></i>
<i class="feather-trash-2"></i>   <i class="feather-eye"></i>
<i class="feather-search"></i>    <i class="feather-user"></i>
<i class="feather-calendar"></i>  <i class="feather-check"></i>
```

---

## Template Tags Disponíveis

| Tag | App | Uso |
|---|---|---|
| `widget_type` | `core` | Detectar tipo de widget: `field.field.widget\|widget_type` |
| `get` | `academic_calendar` | Acessar dict: `by_day\|get:day` |
| `default` | `dashboard` | Valor padrão: `value\|default:"—"` |

---

## Regras

- **Nunca** bootstrap via CDN — usar `{% static 'css/bootstrap.min.css' %}`
- **Nunca** `{% csrf_token %}` omitido em `<form method="post">`
- **Nunca** `{% load static %}` esquecido quando usar `{% static %}`
- **Sempre** `{% block title %}` com nome da tela
- **Sempre** breadcrumb em listagens e formulários
- **Sempre** `{% empty %}` em tabelas para estado vazio
- Consultar `design_system/design-system.html` para referência visual dos componentes Duralux
- Consultar `.github/instructions/templates.instructions.md` para exemplos completos de código

---

## Princípios

- **Server-side rendering first:** toda renderização inicial é feita pelo Django Templates.
- **HTMX para atualizações parciais:** recarregar apenas o fragmento relevante, não a página inteira.
- **Alpine.js para estado local:** não usar Alpine.js para lógica de negócio ou chamadas de API.
- **Sem JavaScript custom complexo:** se precisar de mais de ~20 linhas de JS, rever o design.

---

## Padrões de Templates

### Estrutura de diretórios

```
templates/
    base.html              — layout raiz (head, navbar, sidebar, footer)
    partials/              — fragmentos reutilizáveis (breadcrumb, pagination, etc.)
<app>/
    templates/<app>/
        list.html          — listagem com paginação
        create.html        — formulário de criação
        edit.html          — formulário de edição
        detail.html        — visualização detalhada
        _form.html         — fragmento de formulário (usado por HTMX)
        _row.html          — linha de tabela (usado por HTMX para atualização parcial)
```

### HTMX — padrões

```html
<!-- Submit de form sem reload -->
<form hx-post="{% url 'app:create' %}" hx-target="#result" hx-swap="innerHTML">
    {% csrf_token %}
    ...
</form>

<!-- Recarregar lista após ação -->
<button hx-post="{% url 'app:deactivate' pk=obj.pk %}"
        hx-target="#object-list"
        hx-swap="outerHTML"
        hx-confirm="Confirmar desativação?">
    Desativar
</button>

<!-- Polling para atualização automática -->
<div hx-get="{% url 'dashboard:kpi' %}" hx-trigger="every 30s" hx-swap="innerHTML">
    ...
</div>
```

### Alpine.js — padrões

```html
<!-- Toggle simples -->
<div x-data="{ open: false }">
    <button @click="open = !open">Expandir</button>
    <div x-show="open">Conteúdo oculto</div>
</div>

<!-- Confirmação antes de ação -->
<button x-data
        @click="if (confirm('Confirmar?')) $el.closest('form').submit()">
    Deletar
</button>
```

---

## Formulários

- Usar `django-crispy-forms` ou renderização manual com Bootstrap classes.
- Erros de campo: renderizar ao lado do campo com `is-invalid` + `invalid-feedback`.
- Erros globais do service: usar `messages.error()` no topo do formulário.
- Labels em português, obrigatórios marcados com `*`.

---

## Responsividade

- Layout responsivo obrigatório em todas as telas.
- Mobile-first: testar em viewport 375px.
- Sidebar colapsável em telas < 768px.

---

## Acessibilidade

- `aria-label` em botões que usam apenas ícones.
- `alt` em todas as imagens.
- Contraste mínimo WCAG AA (4.5:1 para texto normal).
