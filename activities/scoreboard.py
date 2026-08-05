"""Preparação de formulários e contexto de apresentação da grade de notas."""

from activities.forms import ActivityScoreForm, ActivityScoresLaunchForm, ActivityScoresReopenForm
from activities.selectors import ActivitySelector


def build_score_rows(activity, data=None, *, guardian_user_id=None):
    """Monta a grade e seus formulários por aluno, preservando POST inválido."""
    submissions = ActivitySelector().list_submissions(
        activity.pk, guardian_user_id=guardian_user_id
    )
    rows = []
    for submission in submissions:
        form = ActivityScoreForm(
            data,
            prefix=f"submission-{submission.pk}",
            initial={
                "score": submission.score,
                "feedback": submission.feedback,
                "submission_id": submission.pk,
                "version": submission.version,
            },
        )
        rows.append({"submission": submission, "form": form})
    return rows


def score_context(
    activity,
    *,
    rows=None,
    saved=None,
    launch_form=None,
    reopen_form=None,
    guardian_user_id=None,
):
    """Monta o contexto de apresentação da grade já carregada."""
    rows = build_score_rows(activity, guardian_user_id=guardian_user_id) if rows is None else rows
    return {
        "score_rows": rows,
        "recorded_count": sum(row["submission"].score is not None for row in rows),
        "total_count": len(rows),
        "saved": saved,
        "guardian_view": guardian_user_id is not None,
        "launch_form": launch_form
        or ActivityScoresLaunchForm(initial={"version": activity.version}),
        "reopen_form": reopen_form
        or ActivityScoresReopenForm(initial={"version": activity.version}),
    }


def apply_score_errors(rows, errors) -> None:
    """Associa erros de domínio aos campos da linha correspondente."""
    forms_by_student = {str(row["submission"].student_id): row["form"] for row in rows}
    for student_id, row_errors in errors.items():
        form = forms_by_student.get(str(student_id))
        if form is None or not isinstance(row_errors, dict):
            continue
        for field, messages_list in row_errors.items():
            target = field if field in form.fields else None
            for message in messages_list:
                form.add_error(target, message)
