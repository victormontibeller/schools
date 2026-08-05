"""Views HTTP da grade e do workflow oficial de notas."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from activities.forms import ActivityScoresLaunchForm, ActivityScoresReopenForm
from activities.presentation import (
    activity_detail_context,
    render_score_card,
    render_score_status_response,
)
from activities.scoreboard import apply_score_errors, build_score_rows
from activities.selectors import ActivitySelector
from activities.services import ActivityService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.forms import apply_validation_errors

logger = logging.getLogger(__name__)


@login_required
def activity_record_score(request, pk):
    """Lança notas e feedbacks da grade pré-carregada."""
    if request.method != "POST":
        return redirect("activity_detail", pk=pk)

    selector = ActivitySelector()
    activity = selector.get_by_id(pk)
    score_rows = build_score_rows(activity, request.POST)
    valid_rows = all(row["form"].is_valid() for row in score_rows)
    for row in score_rows:
        form = row["form"]
        if form.is_valid() and form.cleaned_data["submission_id"] != row["submission"].pk:
            form.add_error("submission_id", "A linha de nota é inválida.")
            valid_rows = False
    if not valid_rows:
        if request.headers.get("HX-Request"):
            return render_score_card(request, activity, rows=score_rows)
        return render(
            request,
            "activities/activity_detail.html",
            activity_detail_context(activity, rows=score_rows),
        )

    rows = [
        {
            "student_id": row["submission"].student_id,
            "score": row["form"].cleaned_data["score"],
            "feedback": row["form"].cleaned_data["feedback"],
            "version": row["form"].cleaned_data["version"],
        }
        for row in score_rows
    ]
    try:
        result = ActivityService(user=request.user).batch_record_scores(pk, rows)
        if result["saved"]:
            messages.success(request, "Notas salvas com sucesso.")
        else:
            messages.info(request, "Nenhuma nota foi alterada.")
        if request.headers.get("HX-Request"):
            return render_score_card(
                request,
                ActivitySelector().get_by_id(pk),
                saved=result["saved"],
            )
        return redirect("activity_detail", pk=pk)
    except (ValidationError, ObjectNotFoundError, BusinessRuleViolationError) as exc:
        activity = selector.get_by_id(pk)
        logger.warning("Erro ao lancar notas", extra={"activity_id": str(pk)})
        if isinstance(exc, ValidationError):
            score_rows = build_score_rows(activity, request.POST)
            for row in score_rows:
                row["form"].is_valid()
            apply_score_errors(score_rows, exc.errors)
        else:
            score_rows = build_score_rows(activity)
        if request.headers.get("HX-Request"):
            return render_score_card(
                request,
                activity,
                rows=score_rows,
                component_error=None if isinstance(exc, ValidationError) else str(exc),
            )
        return render(
            request,
            "activities/activity_detail.html",
            activity_detail_context(
                activity,
                rows=score_rows,
                component_error=None if isinstance(exc, ValidationError) else str(exc),
            ),
        )


def _handle_score_status_transition(request, pk, *, transition):
    """Orquestra o lançamento ou a reabertura e mantém o fallback PRG."""
    if request.method != "POST":
        return redirect("activity_detail", pk=pk)

    selector = ActivitySelector()
    activity = selector.get_by_id(pk)
    form_class = ActivityScoresLaunchForm if transition == "launch" else ActivityScoresReopenForm
    form = form_class(request.POST)
    status_error = None
    if form.is_valid():
        try:
            service = ActivityService(user=request.user)
            if transition == "launch":
                updated = service.launch_scores(pk, form.cleaned_data["version"])
                message = "Notas lançadas oficialmente."
            else:
                updated = service.reopen_scores(
                    pk,
                    form.cleaned_data["version"],
                    form.cleaned_data["reason"],
                )
                message = "Notas reabertas para edição."
            if request.headers.get("HX-Request"):
                return render_score_status_response(
                    request,
                    updated,
                    status_message=message,
                )
            messages.success(request, message)
            return redirect("activity_detail", pk=pk)
        except (ValidationError, ObjectNotFoundError, BusinessRuleViolationError) as exc:
            activity = selector.get_by_id(pk)
            status_error = str(exc)
            if isinstance(exc, ValidationError):
                apply_validation_errors(form, exc)
            else:
                form.add_error(None, str(exc))
            refreshed_form = form_class(initial={"version": activity.version})
            for field_name, errors in form.errors.items():
                target = field_name if field_name in refreshed_form.fields else None
                for error in errors:
                    refreshed_form.add_error(target, error)
            form = refreshed_form

    form_kwargs = {"launch_form": form} if transition == "launch" else {"reopen_form": form}
    status_error = status_error or "Revise os dados do lançamento oficial."
    if request.headers.get("HX-Request"):
        return render_score_status_response(
            request,
            activity,
            status_error=status_error,
            **form_kwargs,
        )
    return render(
        request,
        "activities/activity_detail.html",
        activity_detail_context(activity, status_error=status_error, **form_kwargs),
    )


@login_required
def activity_launch_scores(request, pk):
    """Lança oficialmente a grade de notas da atividade."""
    return _handle_score_status_transition(request, pk, transition="launch")


@login_required
def activity_reopen_scores(request, pk):
    """Reabre a grade oficial mediante motivo obrigatório."""
    return _handle_score_status_transition(request, pk, transition="reopen")
