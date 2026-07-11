"""Views HTMX para grade horária."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from agenda.forms import ScheduleForm, TimeSlotForm
from agenda.selectors import ScheduleSelector, TimeSlotSelector
from agenda.services import ScheduleService
from base.exceptions import BusinessRuleViolationError, ValidationError
from base.listing import build_querystring, build_sorting, resolve_listing_state
from classes.selectors import ClassSelector
from teachers.selectors import TeacherSelector


@login_required
def time_slots_list(request):
    """Lista horários cadastrados usando busca, ordenação e paginação HTMX."""
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="time_slots_list",
        allowed_sorts={
            "day_of_week",
            "-day_of_week",
            "slot_number",
            "-slot_number",
            "start_time",
            "-start_time",
            "end_time",
            "-end_time",
        },
        default_sort="day_of_week",
    )
    search = state["q"]
    sort = state["sort"]
    result = TimeSlotSelector().list_time_slots(search=search, order_by=sort, page=page)
    context = {
        "result": result,
        "q": search,
        "sort": sort,
        "sorting": build_sorting(
            current_sort=sort,
            search=search,
            sortable_fields=["day_of_week", "slot_number", "start_time", "end_time"],
        ),
        "list_query": build_querystring({"q": search, "sort": sort}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Horários", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "agenda/partials/time_slots_table.html", context)
    return render(request, "agenda/time_slots_list.html", context)


@login_required
def time_slot_create(request):
    """Cadastra uma faixa de horário no card compacto padrão."""
    form = TimeSlotForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            ScheduleService(user=request.user).create_time_slot(form.cleaned_data)
            messages.success(request, "Horário cadastrado com sucesso.")
            return redirect("time_slots_list")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    return render(request, "agenda/time_slot_form.html", {"form": form, "title": "Novo Horário"})


@login_required
def time_slot_edit(request, pk):
    """Edita um horário que ainda não foi usado em uma grade."""
    slot = TimeSlotSelector().get_by_id(pk)
    form = TimeSlotForm(request.POST or None, instance=slot)
    if request.method == "POST" and form.is_valid():
        try:
            ScheduleService(user=request.user).update_time_slot(pk, form.cleaned_data)
            messages.success(request, "Horário atualizado com sucesso.")
            return redirect("time_slots_list")
        except (ValidationError, BusinessRuleViolationError) as exc:
            if isinstance(exc, ValidationError):
                for field, errors in exc.errors.items():
                    for error in errors:
                        form.add_error(field if field != "__all__" else None, error)
            else:
                form.add_error(None, exc.message)
    return render(request, "agenda/time_slot_form.html", {"form": form, "title": "Editar Horário"})


@login_required
def schedule_weekly(request, class_id):
    """Exibe a grade horária semanal de uma turma em formato tabela."""
    class_obj = ClassSelector().get_by_id(class_id)
    schedules = ScheduleSelector().get_weekly_schedule(class_obj.pk)
    by_day = ScheduleSelector.group_by_day_of_week(schedules)

    return render(
        request,
        "agenda/schedule_weekly.html",
        {"class_obj": class_obj, "by_day": by_day, "has_schedules": schedules.exists()},
    )


@login_required
def teacher_schedule(request, teacher_id):
    """Exibe a grade horária de um professor."""
    teacher = TeacherSelector().get_by_id(teacher_id)
    schedules = ScheduleSelector().get_teacher_schedule(teacher_id)
    by_day = ScheduleSelector.group_by_day_of_week(schedules)

    return render(
        request,
        "agenda/teacher_schedule.html",
        {"teacher": teacher, "by_day": by_day, "has_schedules": schedules.exists()},
    )


@login_required
def schedule_create(request, class_id):
    """Cria entrada na grade horária de uma turma."""
    form = ScheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        data = {
            "class_obj_id": class_id,
            "teacher_id": cd["teacher"].pk,
            "subject_id": cd["subject"].pk,
            "time_slot_id": cd["time_slot"].pk,
            "room_id": cd["room"].pk if cd["room"] else None,
            "valid_from": cd["valid_from"],
            "valid_until": cd.get("valid_until"),
        }
        try:
            ScheduleService(user=request.user).create_schedule(data)
            return redirect("schedule_weekly", class_id=class_id)
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    return render(
        request,
        "agenda/schedule_form.html",
        {"form": form, "class_id": class_id, "title": "Novo Item de Grade"},
    )
