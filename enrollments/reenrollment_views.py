"""Orquestração HTTP da rematrícula em lote."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    ValidationError,
)
from core.access_catalog import CREATE, REENROLLMENT, VIEW
from core.permissions import access_policy
from enrollments.forms import ReenrollmentSourceForm
from enrollments.selectors import EnrollmentApplicationSelector
from enrollments.services import ReenrollmentService


@login_required
@access_policy(REENROLLMENT, VIEW)
@require_GET
def reenrollment_batch(request):
    """Prepara sugestões de rematrícula sem executar escrita."""
    return render(
        request,
        "enrollments/reenrollment_batch.html",
        _reenrollment_context(request.GET),
    )


@login_required
@access_policy(REENROLLMENT, CREATE)
@require_POST
def reenrollment_batch_confirm(request):
    """Confirma o mapeamento aluno–turma pelo comando atômico canônico."""
    if request.POST.get("form_action") in {"select_all", "clear_selection"}:
        return render(
            request,
            "enrollments/reenrollment_batch.html",
            _reenrollment_context(request.POST),
        )
    try:
        created = ReenrollmentService(user=request.user).confirm_batch(
            _reenrollment_mappings(request.POST)
        )
        messages.success(request, f"Lote confirmado com {len(created)} solicitações.")
        return redirect("reenrollment_batch")
    except (ValidationError, BusinessRuleViolationError, ObjectNotFoundError) as exc:
        messages.error(request, exc.message)
    return render(
        request,
        "enrollments/reenrollment_batch.html",
        _reenrollment_context(request.POST),
    )


def _reenrollment_context(source_data) -> dict:
    form = ReenrollmentSourceForm(source_data or None, class_choices=_class_choices())
    preparation = None
    if form.is_valid():
        preparation = EnrollmentApplicationSelector().reenrollment_candidates(
            form.cleaned_data["source_class_id"]
        )
        submitted = source_data.get("batch_submitted") == "1"
        selected_ids = set(_selected_reenrollment_ids(source_data))
        preselected_target = next(
            (str(item.pk) for item in preparation[2] if getattr(item, "is_preselected", False)),
            "",
        )
        candidates = list(preparation[1])
        selection_action = source_data.get("form_action", "")
        if not submitted or selection_action == "select_all":
            selected_ids = {str(enrollment.pk) for enrollment in candidates}
        elif selection_action == "clear_selection":
            selected_ids = set()
        for enrollment in candidates:
            enrollment_id = str(enrollment.pk)
            enrollment.is_selected_for_batch = enrollment_id in selected_ids if submitted else True
            enrollment.selected_target_id = (
                source_data.get(f"target_{enrollment_id}", "") if submitted else preselected_target
            )
            enrollment.submitted_exception_reason = source_data.get(f"reason_{enrollment_id}", "")
        preparation = (preparation[0], candidates, preparation[2], preparation[3])
    return {"form": form, "preparation": preparation}


def _reenrollment_mappings(source_data) -> list[dict]:
    return [
        {
            "source_enrollment_id": source_id,
            "target_class_id": source_data.get(f"target_{source_id}"),
            "exception_reason": source_data.get(f"reason_{source_id}", ""),
            "expected_version": source_data.get(f"version_{source_id}"),
        }
        for source_id in _selected_reenrollment_ids(source_data)
    ]


def _selected_reenrollment_ids(source_data) -> list[str]:
    """Resolve somente os checkboxes individuais enviados na confirmação."""
    return list(dict.fromkeys(source_data.getlist("source_enrollment_ids")))


def _class_choices() -> list[tuple[str, str]]:
    from classes.selectors import ClassSelector

    return [(str(item.pk), str(item)) for item in ClassSelector().list_ordered()]
