"""Views HTMX para grade horária."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from agenda.forms import ScheduleForm, TimeSlotForm
from agenda.selectors import ScheduleSelector, TimeSlotSelector
from agenda.services import ScheduleService
from base.exceptions import ValidationError
from classes.selectors import ClassSelector
from teachers.selectors import TeacherSelector


@login_required
def time_slots_list(request):
    """Lista horários cadastrados e o formulário de criação."""
    result = TimeSlotSelector().list_time_slots()
    form = TimeSlotForm()
    return render(
        request,
        "agenda/time_slots_list.html",
        {"result": result, "form": form, "title": "Horários"},
    )


@login_required
def time_slot_create(request):
    """Cria uma faixa de horário; redireciona de volta para a lista."""
    if request.method != "POST":
        return redirect("time_slots_list")
    form = TimeSlotForm(request.POST)
    if form.is_valid():
        try:
            ScheduleService(user=request.user).create_time_slot(form.cleaned_data)
        except ValidationError as exc:
            result = TimeSlotSelector().list_time_slots()
            return render(
                request,
                "agenda/time_slots_list.html",
                {"result": result, "form": form, "title": "Horários", "errors": exc.errors},
            )
    return redirect("time_slots_list")


@login_required
def schedule_weekly(request, class_id):
    """Exibe a grade horária semanal de uma turma em formato tabela."""
    class_obj = ClassSelector().get_by_id(class_id)
    schedules = ScheduleSelector().get_weekly_schedule(class_obj.pk)
    by_day = ScheduleSelector.group_by_day_of_week(schedules)

    return render(
        request,
        "agenda/schedule_weekly.html",
        {"class_obj": class_obj, "by_day": by_day},
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
        {"teacher": teacher, "by_day": by_day},
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
