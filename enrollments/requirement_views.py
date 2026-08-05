"""Orquestração HTTP da configuração de requisitos documentais."""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    ValidationError,
)
from base.forms import apply_validation_errors
from base.parsers import parse_optional_int
from core.access_catalog import CREATE, DEACTIVATE, DOCUMENT_REQUIREMENTS, EDIT, VIEW
from core.permissions import access_policy
from enrollments.forms import DocumentRequirementForm
from enrollments.selectors import EnrollmentApplicationSelector
from enrollments.services import StudentDocumentService


@login_required
@access_policy(DOCUMENT_REQUIREMENTS, VIEW)
def document_requirement_list(request):
    """Lista a configuração documental futura, sem alterar snapshots existentes."""
    search = request.GET.get("q", "").strip()
    result = EnrollmentApplicationSelector().list_document_requirements(
        search=search,
        page=parse_optional_int(request.GET.get("page")) or 1,
    )
    context = {
        "result": result,
        "q": search,
        "list_query": urlencode({"q": search}) if search else "",
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Requisitos documentais", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "enrollments/partials/document_requirements_table.html", context)
    return render(request, "enrollments/document_requirement_list.html", context)


@login_required
@access_policy(DOCUMENT_REQUIREMENTS, CREATE)
def document_requirement_create(request):
    """Cadastra requisito a ser copiado em novas solicitações."""
    form = DocumentRequirementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            StudentDocumentService(user=request.user).create_requirement(
                form.cleaned_data,
                expected_version=form.cleaned_data["expected_version"],
            )
            messages.success(request, "Requisito documental criado.")
            return redirect("document_requirement_list")
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "enrollments/document_requirement_form.html",
        {"form": form, "title": "Novo requisito documental"},
    )


@login_required
@access_policy(DOCUMENT_REQUIREMENTS, EDIT)
def document_requirement_edit(request, pk):
    """Edita configuração futura usando versão otimista."""
    requirement = EnrollmentApplicationSelector().get_document_requirement_by_id(pk)
    form = DocumentRequirementForm(
        request.POST or None,
        initial=DocumentRequirementForm.initial_for(requirement),
    )
    if request.method == "POST" and form.is_valid():
        try:
            StudentDocumentService(user=request.user).update_requirement(
                pk,
                form.cleaned_data,
                expected_version=form.cleaned_data["expected_version"],
            )
            messages.success(request, "Requisito documental atualizado.")
            return redirect("document_requirement_list")
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "enrollments/document_requirement_form.html",
        {"form": form, "requirement": requirement, "title": "Editar requisito documental"},
    )


@login_required
@access_policy(DOCUMENT_REQUIREMENTS, DEACTIVATE)
def document_requirement_deactivate(request, pk):
    """Desativa requisito futuro preservando checklists já materializados."""
    if request.method == "POST":
        try:
            StudentDocumentService(user=request.user).deactivate_requirement(
                pk,
                expected_version=parse_optional_int(request.POST.get("expected_version")),
            )
            messages.success(request, "Requisito documental desativado.")
        except (BusinessRuleViolationError, ObjectNotFoundError, ValidationError) as exc:
            messages.error(request, exc.message)
    return redirect("document_requirement_list")
