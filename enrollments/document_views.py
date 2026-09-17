"""Orquestração HTTP dos documentos privados da matrícula."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.shortcuts import redirect, render

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.forms import apply_validation_errors
from base.media import private_file_response
from base.parsers import parse_optional_int
from core.access_catalog import EDIT, VIEW
from core.permissions import access_policy, has_unrestricted_tenant_access
from enrollments.forms import DocumentDeliveryForm
from enrollments.selectors import EnrollmentApplicationSelector
from enrollments.services import StudentDocumentService


@login_required
@access_policy("enrollments", EDIT)
def enrollment_document_delivery(request, pk):
    """Registra upload digital ou conferência física do item do checklist."""
    document = EnrollmentApplicationSelector().get_document_by_id(pk)
    is_htmx = request.headers.get("HX-Request") == "true"
    form = DocumentDeliveryForm(
        request.POST or None,
        request.FILES or None,
        initial={"expected_version": document.version},
        allows_physical=document.allows_physical,
    )
    if request.method == "POST" and form.is_valid():
        try:
            StudentDocumentService(user=request.user).record_delivery(
                pk,
                delivery_method=form.cleaned_data["delivery_method"],
                file=form.cleaned_data.get("file"),
                expected_version=form.cleaned_data["expected_version"],
            )
            messages.success(request, "Entrega registrada.")
            if is_htmx:
                from enrollments.presentation import application_detail_context

                detail = EnrollmentApplicationSelector().get_application_detail(
                    document.application_id
                )
                context = application_detail_context(detail, htmx_messages=True)
                context["include_process_card_oob"] = True
                return render(
                    request,
                    "enrollments/partials/application_documents_card.html",
                    context,
                )
            return redirect("enrollment_application_detail", pk=document.application_id)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)
            document = EnrollmentApplicationSelector().get_document_by_id(pk)
            delivery_method = ""
            if hasattr(form, "cleaned_data"):
                delivery_method = form.cleaned_data.get("delivery_method", "")
            form = DocumentDeliveryForm(
                initial={
                    "expected_version": document.version,
                    "delivery_method": delivery_method,
                },
                allows_physical=document.allows_physical,
            )
    context = {
        "form": form,
        "document": document,
        "title": document.requirement_label,
        "htmx_messages": is_htmx,
    }
    if is_htmx:
        return render(
            request,
            "enrollments/partials/document_delivery_form.html",
            context,
        )
    return render(
        request,
        "enrollments/document_form.html",
        context,
    )


@login_required
@access_policy("enrollments", EDIT)
def enrollment_document_action(request, pk):
    """Verifica, recusa ou dispensa um item documental."""
    document = EnrollmentApplicationSelector().get_document_by_id(pk)
    if request.method == "POST":
        service = StudentDocumentService(user=request.user)
        version = parse_optional_int(request.POST.get("expected_version"))
        action = request.POST.get("action", "")
        try:
            if action == "verify":
                service.verify_document(pk, expected_version=version)
            elif action == "reject":
                service.reject_document(
                    pk, request.POST.get("reason", ""), expected_version=version
                )
            elif action == "waive":
                if not has_unrestricted_tenant_access(request.user):
                    raise DjangoPermissionDenied
                service.waive_document(pk, request.POST.get("reason", ""), expected_version=version)
            else:
                raise ValidationError(errors={"action": ["Ação inválida."]})
            messages.success(request, "Documento atualizado.")
        except (ValidationError, BusinessRuleViolationError, PermissionDeniedError) as exc:
            messages.error(request, exc.message)
    if request.headers.get("HX-Request"):
        from enrollments.presentation import application_detail_context

        detail = EnrollmentApplicationSelector().get_application_detail(document.application_id)
        context = application_detail_context(detail, htmx_messages=True)
        context["include_process_card_oob"] = True
        return render(
            request,
            "enrollments/partials/application_documents_card.html",
            context,
        )
    return redirect("enrollment_application_detail", pk=document.application_id)


@login_required
@access_policy("enrollments", VIEW)
def enrollment_document_download(request, pk):
    """Entrega arquivo privado como anexo, sem cache público."""
    document = EnrollmentApplicationSelector().get_document_by_id(pk)
    if not document.file:
        raise ObjectNotFoundError("StudentDocumentFile", str(pk))
    return private_file_response(document.file, as_attachment=True)
