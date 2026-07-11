---
applyTo: "**/views.py"
---

# Views — Padrões Obrigatórios

> Arquitetura HTTP está em `docs/02_ARCHITECTURE.md`; padrões visuais estão em `docs/09_UI_GUIDELINES.md`. Este arquivo cobre apenas a orquestração em views.

Views são **apenas orquestração HTTP**. Sem regras de negócio, sem queries diretas.

```python
"""Views do módulo my_app."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from base.exceptions import BusinessRuleViolationError, ValidationError


# ── Listagem ──────────────────────────────────────────────────────────────────

@login_required
def my_model_list(request: HttpRequest) -> HttpResponse:
    from my_app.selectors import MySelector

    page = int(request.GET.get("page", 1))
    result = MySelector().list_active(page=page)
    return render(request, "my_app/list.html", {"result": result})


# ── Criação ───────────────────────────────────────────────────────────────────

@login_required
def my_model_create(request: HttpRequest) -> HttpResponse:
    from my_app.forms import MyModelForm
    from my_app.services import MyService

    if request.method == "POST":
        form = MyModelForm(request.POST)
        if form.is_valid():
            try:
                MyService(user=request.user).create_entity(form.cleaned_data)
                messages.success(request, "Registro criado com sucesso.")
                return redirect("my_app:list")
            except ValidationError as exc:
                for field, errors in exc.errors.items():
                    form.add_error(field, errors)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        form = MyModelForm()

    return render(request, "my_app/create.html", {"form": form})


# ── Edição ────────────────────────────────────────────────────────────────────

@login_required
def my_model_edit(request: HttpRequest, pk) -> HttpResponse:
    from my_app.forms import MyModelForm
    from my_app.selectors import MySelector
    from my_app.services import MyService

    instance = MySelector().get_by_id(pk)

    if request.method == "POST":
        form = MyModelForm(request.POST, instance=instance)
        if form.is_valid():
            try:
                MyService(user=request.user).update_entity(pk, form.cleaned_data)
                messages.success(request, "Registro atualizado.")
                return redirect("my_app:list")
            except ValidationError as exc:
                for field, errors in exc.errors.items():
                    form.add_error(field, errors)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        form = MyModelForm(instance=instance)

    return render(request, "my_app/edit.html", {"form": form, "instance": instance})


# ── Desativação (HTMX) ───────────────────────────────────────────────────────

@login_required
def my_model_deactivate(request: HttpRequest, pk) -> HttpResponse:
    from my_app.services import MyService

    if request.method == "POST":
        try:
            MyService(user=request.user).deactivate_entity(pk)
            messages.success(request, "Registro desativado.")
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)
    return redirect("my_app:list")
```

## Regras

- **Nunca** `Model.objects.filter()` em view — usar selector
- **Nunca** lógica de negócio em view — usar service
- **Sempre** capturar `ValidationError` e `BusinessRuleViolationError` do service
- **Sempre** `@login_required` (ou verificação de permissão adequada)
- **Nunca** `ObjectNotFoundError` silenciado — deixar propagar para handler 404 global
- Views HTMX: retornar fragmento HTML, não redirect
- Imports de apps externos devem ser feitos dentro das funções para evitar import circular
