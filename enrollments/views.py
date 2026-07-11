"""Views HTMX para secretaria — matriculas, rematriculas e transferencias."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.listing import build_querystring, resolve_listing_state
from enrollments.forms import (
    BulkReenrollForm,
    EnrollmentApplicationForm,
    StudentDocumentForm,
)
from enrollments.models import EnrollmentApplication
from enrollments.selectors import EnrollmentApplicationSelector
from enrollments.services import EnrollmentApplicationService, StudentDocumentService

logger = logging.getLogger(__name__)

APPLICATION_TABS = [
    {
        "id": "pre-matricula",
        "label": "Pre-Matricula",
        "status": EnrollmentApplication.Status.PRE_ENROLLMENT,
    },
    {"id": "analise", "label": "Em Analise", "status": EnrollmentApplication.Status.UNDER_REVIEW},
    {"id": "aprovados", "label": "Aprovados", "status": EnrollmentApplication.Status.APPROVED},
    {
        "id": "matriculados",
        "label": "Matriculados",
        "status": EnrollmentApplication.Status.ENROLLED,
    },
    {"id": "recusados", "label": "Recusados", "status": EnrollmentApplication.Status.REJECTED},
]


@login_required
def secretary_dashboard(request):
    """Tela unica de secretaria com tabs por etapa do processo."""
    tab = request.GET.get("tab", "pre-matricula")
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="secretary",
        allowed_sorts={"name", "-name", "created_at", "-created_at"},
        default_sort="-created_at",
    )
    search = state["q"]

    tab_map = {t["id"]: t["status"] for t in APPLICATION_TABS}
    status = tab_map.get(tab, EnrollmentApplication.Status.PRE_ENROLLMENT)

    selector = EnrollmentApplicationSelector()
    if status in (
        EnrollmentApplication.Status.PRE_ENROLLMENT,
        EnrollmentApplication.Status.UNDER_REVIEW,
    ):
        result = selector.list_pending_review(search=search, page=page)
    else:
        result = selector.list_by_status(status=status, search=search, page=page)

    ctx = {
        "result": result,
        "q": search,
        "tab": tab,
        "tabs": APPLICATION_TABS,
        "list_query": build_querystring({"q": search, "tab": tab}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Secretaria", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "enrollments/partials/applications_table.html", ctx)
    return render(request, "enrollments/secretary_dashboard.html", ctx)


@login_required
def application_create(request):
    """Processa o formulario de criacao de solicitacao de matricula."""
    form = EnrollmentApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            student = data.pop("student", None)
            class_obj = data.pop("class_obj", None)
            previous_class = data.pop("previous_class", None)
            data["student_id"] = student.pk if student else None
            data["class_obj_id"] = class_obj.pk if class_obj else None
            data["previous_class_id"] = previous_class.pk if previous_class else None
            EnrollmentApplicationService(user=request.user).create_application(data)
            messages.success(request, "Solicitacao de matricula criada com sucesso.")
            return redirect("secretary_dashboard")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "enrollments/application_form.html",
        {"form": form, "title": "Nova Solicitacao de Matricula"},
    )


@login_required
def application_detail(request, pk):
    """Exibe detalhes da solicitacao de matricula e seus documentos."""
    application = EnrollmentApplicationSelector().get_application_by_id(pk)
    documents = EnrollmentApplicationSelector().get_documents(application.pk)
    return render(
        request,
        "enrollments/application_detail.html",
        {
            "application": application,
            "documents": documents,
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Secretaria", "url": "secretary_dashboard"},
                {"label": application.application_number, "url": None},
            ],
        },
    )


@login_required
def application_review(request, pk):
    """Acoes de revisao: aprovar, recusar ou solicitar correcao."""
    application = EnrollmentApplicationSelector().get_application_by_id(pk)

    if request.method == "POST":
        action = request.POST.get("action", "")
        reason = request.POST.get("reason", "")
        try:
            svc = EnrollmentApplicationService(user=request.user)
            if action == "approve":
                svc.approve_application(pk)
                messages.success(request, "Solicitacao aprovada.")
            elif action == "reject":
                svc.reject_application(pk, reason)
                messages.success(request, "Solicitacao recusada.")
            elif action == "request_correction":
                svc.request_correction(pk, reason)
                messages.success(request, "Solicitacao de correcao enviada.")
            else:
                messages.error(request, "Acao invalida.")
                return render(
                    request,
                    "enrollments/application_review.html",
                    {"application": application},
                )
            return redirect("secretary_dashboard")
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)

    return render(
        request,
        "enrollments/application_review.html",
        {"application": application},
    )


@login_required
def application_complete_enrollment(request, pk):
    """Efetiva a matricula aprovada, criando o registro em classes.Enrollment."""
    if request.method != "POST":
        return redirect("application_detail", pk=pk)
    try:
        EnrollmentApplicationService(user=request.user).complete_enrollment(pk)
        messages.success(request, "Matricula efetivada com sucesso.")
    except BusinessRuleViolationError as exc:
        messages.error(request, exc.message)
    return redirect("application_detail", pk=pk)


@login_required
def application_cancel(request, pk):
    """Cancela uma solicitacao."""
    if request.method != "POST":
        return redirect("application_detail", pk=pk)
    reason = request.POST.get("reason", "")
    try:
        EnrollmentApplicationService(user=request.user).cancel_application(pk, reason)
        messages.success(request, "Solicitacao cancelada.")
    except BusinessRuleViolationError as exc:
        messages.error(request, exc.message)
    return redirect("secretary_dashboard")


@login_required
def bulk_reenroll_view(request):
    """Tela de rematricula em lote por turma."""
    if request.method == "POST":
        form = BulkReenrollForm(request.POST)
        if form.is_valid():
            from_class_id = form.cleaned_data["from_class"]
            to_academic_year = form.cleaned_data["to_academic_year"]
            try:
                count = EnrollmentApplicationService(user=request.user).bulk_reenroll(
                    from_class_id=from_class_id, to_academic_year=to_academic_year
                )
                messages.success(
                    request,
                    f"Rematricula em lote concluida. {count} solicitacoes criadas.",
                )
                return redirect("secretary_dashboard")
            except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
                messages.error(request, exc.message)
    else:
        form = BulkReenrollForm()
    return render(
        request,
        "enrollments/bulk_reenroll.html",
        {
            "form": form,
            "title": "Rematricula em Lote",
            "breadcrumb_items": [
                {"label": "Home", "url": "dashboard"},
                {"label": "Secretaria", "url": "secretary_dashboard"},
                {"label": "Rematricula em Lote", "url": None},
            ],
        },
    )


@login_required
def document_add(request, application_id=None):
    """Adiciona documento ao checklist do aluno."""
    initial = {}
    if application_id:
        application = EnrollmentApplicationSelector().get_application_by_id(application_id)
        initial["application"] = application
        initial["student"] = application.student

    form = StudentDocumentForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            student = data.pop("student", None)
            application_obj = data.pop("application", None)
            data["student_id"] = student.pk if student else None
            data["application_id"] = application_obj.pk if application_obj else None
            StudentDocumentService(user=request.user).add_document(data)
            messages.success(request, "Documento adicionado.")
            if application_id:
                return redirect("application_detail", pk=application_id)
            return redirect("secretary_dashboard")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "enrollments/document_form.html",
        {
            "form": form,
            "title": "Adicionar Documento",
            "application_id": application_id,
        },
    )


@login_required
def document_verify(request, pk):
    """Marca documento como verificado."""
    if request.method != "POST":
        return _redirect_back(request)
    try:
        StudentDocumentService(user=request.user).verify_document(pk)
        messages.success(request, "Documento verificado.")
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    return _redirect_back(request)


@login_required
def document_reject(request, pk):
    """Recusa um documento."""
    if request.method != "POST":
        return _redirect_back(request)
    reason = request.POST.get("reason", "")
    try:
        StudentDocumentService(user=request.user).reject_document(pk, reason)
        messages.success(request, "Documento recusado.")
    except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    return _redirect_back(request)


@login_required
def document_download(request, pk):
    """Entrega documento privado como anexo após autorização tenant/RBAC."""
    document = EnrollmentApplicationSelector().get_document_by_id(pk)
    if not document.file:
        raise ObjectNotFoundError("StudentDocumentFile", str(pk))
    response = FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=document.file.name.rsplit("/", maxsplit=1)[-1],
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def notify_pending_documents(request, student_id):
    """Dispara notificacao de pendencias documentais para o aluno/responsavel."""
    if request.method != "POST":
        return _redirect_back(request)
    try:
        from django.db import connection

        from enrollments.tasks import send_pending_documents_notification

        send_pending_documents_notification.delay(
            tenant_schema=getattr(connection, "schema_name", "public"),
            student_id=str(student_id),
        )
        messages.success(request, "Notificacao de pendencias enviada.")
    except (ConnectionError, OSError) as exc:
        logger.warning("Falha ao enfileirar notificacao de pendencias: %s", exc)
        messages.error(request, "Erro ao enviar notificacao. Tente novamente.")
    return _redirect_back(request)


def _redirect_back(request):
    """Redireciona de volta para a pagina anterior ou para o dashboard da secretaria."""
    referer = request.headers.get("Referer", "")
    target = referer or "/app/secretaria/"
    if request.headers.get("HX-Request"):
        return HttpResponse(status=204, headers={"HX-Redirect": target})
    return redirect(target)
