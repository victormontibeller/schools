"""Views HTMX para atividades."""

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from activities.forms import ActivityForm, ScoreForm
from activities.selectors import ActivitySelector
from activities.services import ActivityService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError

logger = logging.getLogger(__name__)


@login_required
def activities_list(request):
    """Lista atividades paginadas; filtra por turma quando ?class_obj=."""
    page = int(request.GET.get("page", 1))
    class_obj_filter = request.GET.get("class_obj", "").strip()
    search = request.GET.get("q", "").strip()
    filters = {}
    if class_obj_filter:
        filters["class_obj_id"] = class_obj_filter
    if search:
        filters["title__icontains"] = search

    result = ActivitySelector().list_activities(filters=filters, page=page)
    ctx = {
        "result": result,
        "q": search,
        "class_obj_filter": class_obj_filter,
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Atividades", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "activities/partials/activities_table.html", ctx)
    return render(request, "activities/activities_list.html", ctx)


@login_required
def activity_create(request):
    """Exibe/Processa criação de atividade."""
    form = ActivityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cd = form.cleaned_data
            ActivityService(user=request.user).create_activity(
                {
                    "class_obj_id": cd["class_obj"].pk,
                    "subject_id": cd["subject"].pk,
                    "teacher_id": cd["teacher"].pk,
                    "title": cd["title"],
                    "description": cd.get("description", ""),
                    "type": cd["type"],
                    "due_date": cd["due_date"],
                    "max_score": cd["max_score"],
                    "weight": cd["weight"],
                }
            )
            return redirect("activities_list")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    return render(
        request,
        "activities/activity_form.html",
        {"form": form, "title": "Nova Atividade"},
    )


@login_required
def activity_detail(request, pk):
    """Exibe atividade e lista de entregas/notas."""
    from activities.forms import ScoreForm

    activity = ActivitySelector().get_by_id(pk)
    submissions = ActivitySelector().list_submissions(activity.pk)
    return render(
        request,
        "activities/activity_detail.html",
        {"activity": activity, "submissions": submissions, "form": ScoreForm()},
    )


@login_required
def activity_record_score(request, pk):
    """Lança nota de um aluno numa atividade (POST via HTMX)."""
    if request.method != "POST":
        return redirect("activity_detail", pk=pk)

    form = ScoreForm(request.POST)
    if form.is_valid():
        try:
            ActivityService(user=request.user).record_score(
                pk,
                form.cleaned_data["student"].pk,
                form.cleaned_data["score"],
                form.cleaned_data.get("feedback", ""),
            )
        except (ValidationError, ObjectNotFoundError, BusinessRuleViolationError) as exc:
            logger.warning("Erro ao lancar nota: %s", exc, extra={"activity_id": str(pk)})
            from django.contrib import messages

            messages.error(request, str(exc))
    return redirect("activity_detail", pk=pk)
