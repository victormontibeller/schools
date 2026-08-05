"""Views HTMX para atividades."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from activities.forms import (
    ActivityEditForm,
    ActivityForm,
    ActivityGroupForm,
    ActivityGroupResultForm,
)
from activities.presentation import (
    activity_detail_context,
    group_rows,
    information_context,
    render_groups_card,
)
from activities.selectors import ActivitySelector
from activities.services import ActivityService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_querystring, build_sorting, resolve_listing_state


@login_required
def activities_list(request):
    """Lista atividades paginadas; filtra por turma quando ?class_obj=."""
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
            "modality",
            "-modality",
            "due_date",
            "-due_date",
            "max_score",
            "-max_score",
        },
        default_sort="-due_date",
    )
    search, sort = state["q"], state["sort"]
    filters = {}
    role_name = getattr(getattr(request.user, "role", None), "name", "")
    if class_obj_filter:
        filters["class_obj_id"] = class_obj_filter
    if search:
        filters["title__icontains"] = search

    result = ActivitySelector().list_activities_for_user(
        user_id=request.user.pk,
        role_name=role_name,
        filters=filters,
        order_by=sort,
        page=state["page"],
    )
    ctx = {
        "result": result,
        "q": search,
        "sort": sort,
        "sorting": build_sorting(
            current_sort=sort,
            search=search,
            sortable_fields=[
                "title",
                "class_obj",
                "subject",
                "type",
                "modality",
                "due_date",
                "max_score",
            ],
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
    form = ActivityForm(request.POST or None, user=request.user)
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
                    "modality": cd["modality"],
                    "due_date": cd["due_date"],
                    "max_score": cd["max_score"],
                    "weight": cd["weight"],
                }
            )
            return redirect("activities_list")
        except ValidationError as exc:
            apply_validation_errors(form, exc)
    return render(
        request,
        "activities/activity_form.html",
        {"form": form, "title": "Nova Atividade"},
    )


@login_required
def activity_detail(request, pk):
    """Exibe atividade e lista de entregas/notas."""
    activity = ActivitySelector().get_by_id(pk)
    role_name = getattr(getattr(request.user, "role", None), "name", "")
    guardian_user_id = request.user.pk if role_name == "GUARDIAN" else None
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "activities/partials/activity_information_card.html",
            information_context(activity),
        )
    if (
        guardian_user_id is None
        and request.headers.get("HX-Request")
        and request.GET.get("component") == "groups"
    ):
        return render_groups_card(request, activity)
    return render(
        request,
        "activities/activity_detail.html",
        activity_detail_context(activity, guardian_user_id=guardian_user_id),
    )


@login_required
def activity_edit(request, pk):
    """Edita a atividade substituindo apenas o card de informações."""
    activity = ActivitySelector().get_by_id(pk)
    form = ActivityEditForm(
        request.POST or None,
        user=request.user,
        initial={
            "class_obj": activity.class_obj,
            "subject": activity.subject,
            "teacher": activity.teacher,
            "title": activity.title,
            "description": activity.description,
            "type": activity.type,
            "modality": activity.modality,
            "due_date": activity.due_date,
            "max_score": activity.max_score,
            "weight": activity.weight,
            "version": activity.version,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            activity = ActivityService(user=request.user).update_activity(pk, form.cleaned_data)
            if request.headers.get("HX-Request"):
                return render(
                    request,
                    "activities/partials/activity_information_card.html",
                    information_context(activity, saved=True),
                )
            return redirect("activity_detail", pk=pk)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, str(exc))
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
def activity_group_save(request, pk, group_id=None):
    """Cria ou edita a composição de um grupo da atividade."""
    selector = ActivitySelector()
    activity = selector.get_by_id(pk)
    group = selector.get_group(pk, group_id) if group_id else None
    initial = None
    if group:
        initial = {
            "name": group.name,
            "students": [membership.student_id for membership in group.memberships.all()],
        }
    form = ActivityGroupForm(request.POST or None, activity=activity, initial=initial)
    if request.method == "GET":
        if not request.headers.get("HX-Request"):
            return redirect("activity_detail", pk=pk)
        return render(
            request,
            "activities/partials/activity_group_form_card.html",
            {
                "activity": activity,
                "group": group,
                "form": form,
                "title": "Editar grupo" if group else "Novo grupo",
                "action_url": request.path,
            },
        )
    if form.is_valid():
        try:
            ActivityService(user=request.user).save_group(
                pk,
                {
                    "name": form.cleaned_data["name"],
                    "student_ids": [student.pk for student in form.cleaned_data["students"]],
                },
                group_id=group_id,
            )
            if request.headers.get("HX-Request"):
                return render_groups_card(request, activity, saved=True)
            messages.success(request, "Grupo salvo com sucesso.")
            return redirect("activity_detail", pk=pk)
        except (ValidationError, BusinessRuleViolationError) as exc:
            form.add_error(None, str(exc))
    if request.headers.get("HX-Request"):
        return render(
            request,
            "activities/partials/activity_group_form_card.html",
            {
                "activity": activity,
                "group": group,
                "form": form,
                "title": "Editar grupo" if group else "Novo grupo",
                "action_url": request.path,
            },
        )
    messages.error(request, "Revise o nome e os integrantes do grupo.")
    return redirect("activity_detail", pk=pk)


@login_required
def activity_group_apply_result(request, pk, group_id):
    """Reaplica explicitamente nota e feedback do grupo aos integrantes."""
    if request.method != "POST":
        return redirect("activity_detail", pk=pk)
    activity = ActivitySelector().get_by_id(pk)
    form = ActivityGroupResultForm(request.POST, prefix=f"group-{group_id}")
    if form.is_valid():
        try:
            ActivityService(user=request.user).apply_group_result(
                pk,
                group_id,
                form.cleaned_data["score"],
                form.cleaned_data["feedback"],
            )
            if request.headers.get("HX-Request"):
                return render_groups_card(request, activity, saved=True)
            messages.success(request, "Resultado do grupo aplicado aos integrantes.")
            return redirect("activity_detail", pk=pk)
        except (ValidationError, ObjectNotFoundError, BusinessRuleViolationError) as exc:
            form.add_error(None, str(exc))
    if request.headers.get("HX-Request"):
        return render_groups_card(
            request,
            activity,
            group_rows=group_rows(activity, form, group_id),
        )
    messages.error(request, "Revise o resultado coletivo.")
    return redirect("activity_detail", pk=pk)


@login_required
def activity_group_deactivate(request, pk, group_id):
    """Desativa um grupo mantendo os resultados individuais."""
    if request.method == "POST":
        activity = ActivitySelector().get_by_id(pk)
        try:
            ActivityService(user=request.user).deactivate_group(pk, group_id)
            if request.headers.get("HX-Request"):
                return render_groups_card(request, activity, saved=True)
            messages.success(request, "Grupo desativado com sucesso.")
        except (ValidationError, ObjectNotFoundError, BusinessRuleViolationError) as exc:
            if request.headers.get("HX-Request"):
                return render_groups_card(request, activity, component_error=str(exc))
            messages.error(request, str(exc))
    return redirect("activity_detail", pk=pk)
