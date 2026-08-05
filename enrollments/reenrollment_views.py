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
    return {"form": form, "preparation": preparation}


def _reenrollment_mappings(source_data) -> list[dict]:
    return [
        {
            "source_enrollment_id": source_id,
            "target_class_id": source_data.get(f"target_{source_id}"),
            "exception_reason": source_data.get(f"reason_{source_id}", ""),
            "expected_version": source_data.get(f"version_{source_id}"),
        }
        for source_id in source_data.getlist("source_enrollment_ids")
        if source_data.get(f"target_{source_id}")
    ]


def _class_choices() -> list[tuple[str, str]]:
    from classes.selectors import ClassSelector

    return [(str(item.pk), str(item)) for item in ClassSelector().list_ordered()]
