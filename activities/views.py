"""Views HTMX para atividades."""

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from activities.forms import ActivityEditForm, ActivityForm
from activities.selectors import ActivitySelector
from activities.services import ActivityService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.listing import build_querystring, build_sorting, resolve_listing_state

logger = logging.getLogger(__name__)


@login_required
def activities_list(request):
    """Lista atividades paginadas; filtra por turma quando ?class_obj=."""
    page = int(request.GET.get("page", 1))
    class_obj_filter = request.GET.get("class_obj", "").strip()
    state = resolve_listing_state(
        request,
        scope="activities_list",
        allowed_sorts={
            "title",
            "-title",
            "class_obj",
            "-class_obj",
            "subject",
            "-subject",
            "type",
            "-type",
            "due_date",
            "-due_date",
            "max_score",
            "-max_score",
        },
        default_sort="-due_date",
    )
    search, sort = state["q"], state["sort"]
    filters = {}
    if class_obj_filter:
        filters["class_obj_id"] = class_obj_filter
    if search:
        filters["title__icontains"] = search

    result = ActivitySelector().list_activities(filters=filters, order_by=sort, page=page)
    ctx = {
        "result": result,
        "q": search,
        "sort": sort,
        "sorting": build_sorting(
            current_sort=sort,
            search=search,
            sortable_fields=["title", "class_obj", "subject", "type", "due_date", "max_score"],
        ),
        "list_query": build_querystring({"q": search, "class_obj": class_obj_filter, "sort": sort}),
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
    activity = ActivitySelector().get_by_id(pk)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "activities/partials/activity_information_card.html",
            {"activity": activity},
        )
    submissions = ActivitySelector().list_submissions(activity.pk)
    return render(
        request,
        "activities/activity_detail.html",
        {"activity": activity, "submissions": submissions},
    )


@login_required
def activity_edit(request, pk):
    """Edita a atividade substituindo apenas o card de informações."""
    activity = ActivitySelector().get_by_id(pk)
    form = ActivityEditForm(
        request.POST or None,
        initial={
            "class_obj": activity.class_obj,
            "subject": activity.subject,
            "teacher": activity.teacher,
            "title": activity.title,
            "description": activity.description,
            "type": activity.type,
            "due_date": activity.due_date,
            "max_score": activity.max_score,
            "weight": activity.weight,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            activity = ActivityService(user=request.user).update_activity(pk, form.cleaned_data)
            if request.headers.get("HX-Request"):
                return render(
                    request,
                    "activities/partials/activity_information_card.html",
                    {"activity": activity, "saved": True},
                )
            return redirect("activity_detail", pk=pk)
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    if not request.headers.get("HX-Request"):
        return redirect("activity_detail", pk=pk)
    return render(
        request,
        "partials/information_form_card.html",
        {
            "form": form,
            "component_id": "activity-information-card",
            "component_title": "Informações da Atividade",
            "edit_url": request.path,
            "cancel_url": f"{request.path_info.removesuffix('editar/')}?component=information",
        },
    )


@login_required
def activity_record_score(request, pk):
    """Lança notas e feedbacks da grade pré-carregada."""
    if request.method != "POST":
        return redirect("activity_detail", pk=pk)

    submissions = ActivitySelector().list_submissions(pk)
    rows = [
        {
            "student_id": submission.student_id,
            "score": request.POST.get(f"score_{submission.student_id}", ""),
            "feedback": request.POST.get(f"feedback_{submission.student_id}", ""),
        }
        for submission in submissions
    ]
    try:
        ActivityService(user=request.user).batch_record_scores(pk, rows)
    except (ValidationError, ObjectNotFoundError, BusinessRuleViolationError) as exc:
        logger.warning("Erro ao lancar notas", extra={"activity_id": str(pk)})
        from django.contrib import messages

        messages.error(request, str(exc))
    return redirect("activity_detail", pk=pk)
