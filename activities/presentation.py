"""Contextos e fragments de apresentação da ficha de atividade."""

from django.shortcuts import render

from activities.forms import ActivityGroupResultForm
from activities.scoreboard import score_context
from activities.selectors import ActivitySelector


def group_rows(activity, result_form=None, result_group_id=None):
    """Monta os formulários de resultado exibidos no card de grupos."""
    rows = []
    for group in ActivitySelector().list_groups(activity.pk):
        form = (
            result_form
            if group.pk == result_group_id
            else ActivityGroupResultForm(
                prefix=f"group-{group.pk}",
                initial={"score": group.score, "feedback": group.feedback},
            )
        )
        rows.append({"group": group, "result_form": form})
    return rows


def render_groups_card(request, activity, **context):
    """Renderiza o menor fragmento estável da gestão de grupos."""
    context.setdefault("group_rows", group_rows(activity))
    context["activity"] = activity
    return render(request, "activities/partials/activity_groups_card.html", context)


def render_score_card(
    request,
    activity,
    *,
    rows=None,
    saved=None,
    launch_form=None,
    reopen_form=None,
    status_message=None,
    component_error=None,
):
    """Renderiza exclusivamente o card substituível da grade de notas."""
    context = {
        "activity": activity,
        "status_message": status_message,
        "component_error": component_error,
        **score_context(
            activity,
            rows=rows,
            saved=saved,
            launch_form=launch_form,
            reopen_form=reopen_form,
        ),
    }
    return render(request, "activities/partials/activity_score_card.html", context)


def render_score_status_response(
    request,
    activity,
    *,
    launch_form=None,
    reopen_form=None,
    status_message=None,
    status_error=None,
):
    """Atualiza os cards afetados por uma transição do workflow de notas."""
    context = {
        "activity": activity,
        "group_rows": group_rows(activity),
        "status_message": status_message,
        "status_error": status_error,
        **score_context(
            activity,
            launch_form=launch_form,
            reopen_form=reopen_form,
        ),
    }
    return render(request, "activities/partials/activity_score_status_response.html", context)


def activity_detail_context(
    activity,
    *,
    guardian_user_id=None,
    component_error=None,
    status_message=None,
    status_error=None,
    **score_kwargs,
):
    """Monta o contexto completo da ficha para o fallback sem JavaScript."""
    return {
        "activity": activity,
        "group_rows": [] if guardian_user_id is not None else group_rows(activity),
        "guardian_view": guardian_user_id is not None,
        "component_error": component_error,
        "status_message": status_message,
        "status_error": status_error,
        **score_context(activity, guardian_user_id=guardian_user_id, **score_kwargs),
    }


def information_context(activity, **context):
    """Monta o contexto do card de informações, inclusive controles de status."""
    return {"activity": activity, **score_context(activity), **context}
