"""Orquestração HTTP da configuração de períodos comuns."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from agenda.forms import TimeSlotForm
from agenda.selectors import TimeSlotSelector
from agenda.services import ScheduleService
from base.exceptions import BusinessRuleViolationError, ValidationError
from base.forms import apply_validation_errors
from core.permissions import access_policy


@login_required
@access_policy("schedule_configuration", "view")
def time_slots_list(request: HttpRequest) -> HttpResponse:
    """Lista os períodos comuns que estruturam todas as matrizes."""
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    context = {
        "result": TimeSlotSelector().list_ordered(page=page),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Períodos", "url": None},
        ],
    }
    template_name = (
        "agenda/partials/time_slots_table.html"
        if request.headers.get("HX-Request")
        else "agenda/time_slots_list.html"
    )
    return render(request, template_name, context)


@login_required
@access_policy("schedule_configuration", "create")
def time_slot_create(request: HttpRequest) -> HttpResponse:
    """Cria um período comum sem duplicar a regra de intervalos da aplicação."""
    form = TimeSlotForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            ScheduleService(user=request.user).create_time_slot(form.cleaned_data)
            messages.success(request, "Período cadastrado com sucesso.")
            return redirect("time_slots_list")
        except ValidationError as exc:
            apply_validation_errors(form, exc)
    return render(request, "agenda/time_slot_form.html", {"form": form, "title": "Novo período"})


@login_required
@access_policy("schedule_configuration", "edit")
def time_slot_edit(request: HttpRequest, pk) -> HttpResponse:
    """Edita um período que ainda não participa de qualquer versão da matriz."""
    slot = TimeSlotSelector().get_by_id(pk)
    form = TimeSlotForm(request.POST or None, instance=slot)
    if request.method == "POST" and form.is_valid():
        try:
            ScheduleService(user=request.user).update_time_slot(pk, form.cleaned_data)
            messages.success(request, "Período atualizado com sucesso.")
            return redirect("time_slots_list")
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
    return render(request, "agenda/time_slot_form.html", {"form": form, "title": "Editar período"})
