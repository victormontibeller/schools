"""Orquestração HTTP das células e da cópia da matriz semanal."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from agenda.forms import ScheduleCellForm, ScheduleCopyDayForm, ScheduleEndForm
from agenda.presentation import (
    as_of_from_request,
    cell_action_url,
    copy_day_initial,
    is_component_htmx_request,
    matrix_context,
    matrix_url,
    week_monday,
)
from agenda.selectors import ScheduleSelector, TimeSlotSelector
from agenda.services import ScheduleService
from base.exceptions import BusinessRuleViolationError, ValidationError
from base.forms import apply_validation_errors
from core.permissions import access_policy, role_name


def _cell_form_response(request: HttpRequest, template_name: str, context: dict) -> HttpResponse:
    if is_component_htmx_request(request):
        return render(request, template_name, {**context, "modal_response": True})
    return render(request, "agenda/schedule_cell_form_page.html", context)


def _copy_form_response(request: HttpRequest, context: dict) -> HttpResponse:
    if is_component_htmx_request(request):
        return render(
            request,
            "agenda/partials/schedule_copy_day_form.html",
            {**context, "modal_response": True},
        )
    return render(request, "agenda/schedule_copy_day_form_page.html", context)


@login_required
@access_policy("schedule", "create")
def schedule_cell_create(request: HttpRequest, class_id, day_of_week, time_slot_id) -> HttpResponse:
    """Renderiza e cria a célula vazia selecionada na matriz."""
    as_of = as_of_from_request(request)
    selector = ScheduleSelector()
    day_label = dict(selector.day_choices()).get(day_of_week)
    if day_label is None:
        raise Http404("Dia letivo inválido.")
    class_obj = selector.get_class_for_matrix(
        class_id,
        user_id=request.user.pk,
        role_name=role_name(request.user),
        as_of=as_of,
    )
    time_slot = TimeSlotSelector().get_compatible_for_class(time_slot_id, class_id)
    form = ScheduleCellForm(
        request.POST or None,
        choices=selector.get_cell_choices(),
        initial={"valid_from": as_of},
    )
    if request.method == "POST" and form.is_valid():
        try:
            schedule = ScheduleService(user=request.user).create_schedule(
                {
                    **form.cleaned_data,
                    "class_obj_id": class_id,
                    "day_of_week": day_of_week,
                    "time_slot_id": time_slot_id,
                }
            )
            return _schedule_response(request, class_id, as_of, schedule)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
    return _cell_form_response(
        request,
        "agenda/partials/schedule_cell_form.html",
        {
            "form": form,
            "class_id": class_id,
            "class_obj": class_obj,
            "day_of_week": day_of_week,
            "day_label": day_label,
            "time_slot_id": time_slot_id,
            "time_slot": time_slot,
            "as_of": as_of,
            "title": "Adicionar aula",
            "submit_label": "Salvar",
            "form_action": cell_action_url(
                "schedule_cell_create", class_id, day_of_week, time_slot_id, as_of=as_of
            ),
            "cancel_url": matrix_url(class_id, as_of),
        },
    )


@login_required
@access_policy("schedule", "edit")
def schedule_cell_edit(request: HttpRequest, class_id, schedule_id) -> HttpResponse:
    """Cria uma versão sucessora da célula a partir da data de referência."""
    as_of = as_of_from_request(request)
    selector = ScheduleSelector()
    class_obj = selector.get_class_for_matrix(
        class_id,
        user_id=request.user.pk,
        role_name=role_name(request.user),
        as_of=as_of,
    )
    schedule = selector.get_schedule_for_class(class_id, schedule_id)
    form = ScheduleCellForm(
        request.POST or None,
        choices=selector.get_cell_choices(),
        initial={
            "teacher_id": str(schedule.teacher_id),
            "subject_id": str(schedule.subject_id),
            "room_id": str(schedule.room_id or ""),
            "valid_from": as_of,
            "valid_until": schedule.valid_until,
            "version": schedule.version,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            successor = ScheduleService(user=request.user).create_schedule_successor(
                schedule_id,
                {
                    **form.cleaned_data,
                    "class_obj_id": class_id,
                    "day_of_week": schedule.day_of_week,
                    "time_slot_id": schedule.time_slot_id,
                },
            )
            if not is_component_htmx_request(request):
                messages.success(request, "Nova versão da célula criada.")
            return _schedule_response(request, class_id, as_of, successor)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
    return _cell_form_response(
        request,
        "agenda/partials/schedule_cell_form.html",
        {
            "form": form,
            "class_id": class_id,
            "class_obj": class_obj,
            "schedule": schedule,
            "day_of_week": schedule.day_of_week,
            "day_label": schedule.get_day_of_week_display(),
            "time_slot": schedule.time_slot,
            "as_of": as_of,
            "title": "Editar aula",
            "submit_label": "Salvar",
            "form_action": cell_action_url(
                "schedule_cell_edit", class_id, schedule.pk, as_of=as_of
            ),
            "cancel_url": matrix_url(class_id, as_of),
        },
    )


@login_required
@access_policy("schedule", "edit")
def schedule_cell_end(request: HttpRequest, class_id, schedule_id) -> HttpResponse:
    """Renderiza e encerra a versão atual da célula sem apagar seu histórico."""
    as_of = as_of_from_request(request)
    selector = ScheduleSelector()
    class_obj = selector.get_class_for_matrix(
        class_id,
        user_id=request.user.pk,
        role_name=role_name(request.user),
        as_of=as_of,
    )
    schedule = selector.get_schedule_for_class(class_id, schedule_id)
    form = ScheduleEndForm(
        request.POST or None, initial={"valid_until": as_of, "version": schedule.version}
    )
    if request.method == "POST" and form.is_valid():
        try:
            ended = ScheduleService(user=request.user).end_schedule(schedule_id, form.cleaned_data)
            if not is_component_htmx_request(request):
                messages.success(request, "Célula encerrada.")
            return _schedule_response(
                request,
                class_id,
                as_of,
                ended if ended.valid_until >= as_of else None,
                day_of_week=ended.day_of_week,
                time_slot_id=ended.time_slot_id,
            )
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
    return _cell_form_response(
        request,
        "agenda/partials/schedule_cell_form.html",
        {
            "form": form,
            "class_id": class_id,
            "class_obj": class_obj,
            "schedule": schedule,
            "day_of_week": schedule.day_of_week,
            "day_label": schedule.get_day_of_week_display(),
            "time_slot": schedule.time_slot,
            "as_of": as_of,
            "title": "Encerrar aula",
            "submit_label": "Encerrar",
            "form_action": cell_action_url("schedule_cell_end", class_id, schedule.pk, as_of=as_of),
            "cancel_url": matrix_url(class_id, as_of),
        },
    )


@login_required
@access_policy("schedule", "create")
def schedule_day_copy_form(request: HttpRequest, class_id) -> HttpResponse:
    """Exibe o formulário canônico de cópia de dia para a matriz selecionada."""
    as_of = as_of_from_request(request)
    selector = ScheduleSelector()
    class_obj = selector.get_class_for_matrix(
        class_id,
        user_id=request.user.pk,
        role_name=role_name(request.user),
        as_of=as_of,
    )
    day_choices = selector.day_choices()
    return _copy_form_response(
        request,
        {
            "class_id": class_id,
            "class_obj": class_obj,
            "as_of": as_of,
            "form": ScheduleCopyDayForm(
                initial=copy_day_initial(as_of, day_choices), day_choices=day_choices
            ),
            "title": "Copiar dia",
            "form_action": cell_action_url("schedule_day_copy", class_id, as_of=as_of),
            "cancel_url": matrix_url(class_id, as_of),
        },
    )


@login_required
@access_policy("schedule", "create")
@require_POST
def schedule_day_copy(request: HttpRequest, class_id) -> HttpResponse:
    """Copia o dia selecionado com validação completa antes de qualquer escrita."""
    as_of = as_of_from_request(request)
    selector = ScheduleSelector()
    class_obj = selector.get_class_for_matrix(
        class_id,
        user_id=request.user.pk,
        role_name=role_name(request.user),
        as_of=as_of,
    )
    day_choices = selector.day_choices()
    form = ScheduleCopyDayForm(request.POST or None, day_choices=day_choices)
    if form.is_valid():
        try:
            copy_data = {**form.cleaned_data, "as_of": week_monday(form.cleaned_data["as_of"])}
            ScheduleService(user=request.user).copy_schedule_day(class_id, copy_data)
            if not is_component_htmx_request(request):
                messages.success(request, "Dia copiado para a matriz.")
            if is_component_htmx_request(request):
                response = render(
                    request,
                    "agenda/partials/schedule_matrix_workspace.html",
                    {
                        **matrix_context(request.user, class_id, copy_data["as_of"]),
                        "workspace_oob": True,
                    },
                )
                response["HX-Trigger-After-Settle"] = json.dumps(
                    {"schedule-day-copied": {"returnFocus": "schedule-copy-day-trigger"}}
                )
                response["HX-Push-Url"] = matrix_url(class_id, copy_data["as_of"])
                return response
            return redirect(matrix_url(class_id, copy_data["as_of"]))
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
    return _copy_form_response(
        request,
        {
            "class_id": class_id,
            "class_obj": class_obj,
            "as_of": as_of,
            "form": form,
            "title": "Copiar dia",
            "form_action": cell_action_url("schedule_day_copy", class_id, as_of=as_of),
            "cancel_url": matrix_url(class_id, as_of),
        },
    )


def _schedule_response(
    request: HttpRequest, class_id, as_of, schedule, day_of_week="", time_slot_id=""
) -> HttpResponse:
    if not is_component_htmx_request(request):
        return redirect(matrix_url(class_id, as_of))
    day_of_week = getattr(schedule, "day_of_week", day_of_week)
    time_slot_id = getattr(schedule, "time_slot_id", time_slot_id)
    visible_schedule = (
        ScheduleSelector().get_effective_schedule(class_id, day_of_week, time_slot_id, as_of)
        if day_of_week and time_slot_id
        else None
    )
    response = render(
        request,
        "agenda/partials/schedule_cell_modal_success.html",
        {
            "class_id": class_id,
            "schedule": visible_schedule,
            "as_of": as_of,
            "day_of_week": day_of_week,
            "time_slot_id": time_slot_id,
        },
    )
    response["HX-Trigger-After-Settle"] = json.dumps(
        {
            "schedule-cell-saved": {
                "returnFocus": (
                    f"schedule-cell-{day_of_week}-{time_slot_id}-"
                    f"{'edit' if visible_schedule else 'create'}"
                )
            }
        }
    )
    return response
