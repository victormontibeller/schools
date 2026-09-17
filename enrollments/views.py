"""Orquestração HTTP do workflow interno de matrículas."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    ValidationError,
)
from base.forms import apply_validation_errors
from base.listing import build_listing_tabs, build_querystring
from base.parsers import parse_optional_int, parse_optional_uuid
from core.access_catalog import CREATE, EDIT, VIEW
from core.permissions import access_policy
from enrollments.contracts import EnrollmentApplication, StudentDocument
from enrollments.forms import (
    EnrollmentApplicationCorrectionForm,
    EnrollmentApplicationForm,
)
from enrollments.presentation import (
    application_detail_context,
    application_form_choices,
    class_choices,
)
from enrollments.selectors import EnrollmentApplicationSelector
from enrollments.services import (
    EnrollmentApplicationService,
    EnrollmentReminderService,
)

APPLICATION_TABS = (
    ("pre-matriculas", "Pré-matrículas", [EnrollmentApplication.Status.PRE_ENROLLMENT]),
    ("correcoes", "Correções", [EnrollmentApplication.Status.CORRECTION_REQUIRED]),
    ("analise", "Em análise", [EnrollmentApplication.Status.UNDER_REVIEW]),
    ("espera", "Lista de espera", [EnrollmentApplication.Status.WAITLISTED]),
    ("aprovadas", "Aprovadas", [EnrollmentApplication.Status.APPROVED]),
    ("matriculadas", "Matriculadas", [EnrollmentApplication.Status.ENROLLED]),
    ("transferidas", "Transferidas", [EnrollmentApplication.Status.TRANSFERRED]),
    (
        "encerradas",
        "Encerradas",
        [EnrollmentApplication.Status.REJECTED, EnrollmentApplication.Status.CANCELLED],
    ),
)


@login_required
@access_policy("enrollments", VIEW)
def enrollment_application_list(request):
    """Exibe listagem canônica com abas, contadores e filtros persistíveis."""
    selector = EnrollmentApplicationSelector()
    requested_tab = request.GET.get("tab", APPLICATION_TABS[0][0])
    tab_definition = next(
        (item for item in APPLICATION_TABS if item[0] == requested_tab), APPLICATION_TABS[0]
    )
    tab = tab_definition[0]
    search = request.GET.get("q", "").strip()
    year = parse_optional_int(request.GET.get("academic_year"))
    normalized_class_id = parse_optional_uuid(request.GET.get("class_id"))
    class_id = str(normalized_class_id) if normalized_class_id else ""
    result = selector.list_applications(
        statuses=tab_definition[2],
        search=search,
        academic_year=year,
        class_id=normalized_class_id,
        application_type=request.GET.get("application_type", ""),
        document_status=request.GET.get("document_status", ""),
        page=parse_optional_int(request.GET.get("page")) or 1,
    )
    counts = selector.status_counts()
    filter_values = {
        key: value
        for key, value in {
            "q": search,
            "academic_year": year or "",
            "class_id": class_id,
            "application_type": request.GET.get("application_type", ""),
            "document_status": request.GET.get("document_status", ""),
        }.items()
        if value not in (None, "")
    }
    tab_counts = {
        item[0]: sum(counts.get(status, 0) for status in item[2]) for item in APPLICATION_TABS
    }
    list_query_values = {**filter_values, "tab": tab}
    is_htmx = bool(request.headers.get("HX-Request"))
    context = {
        "result": result,
        "tab": tab,
        "list_tabs": build_listing_tabs(
            choices=((item[0], item[1]) for item in APPLICATION_TABS),
            active=tab,
            parameter="tab",
            preserved_params=filter_values,
            counts=tab_counts,
        ),
        "list_tabs_label": "Etapas da matrícula",
        "q": search,
        "academic_year": year or "",
        "class_id": class_id,
        "application_type": request.GET.get("application_type", ""),
        "document_status": request.GET.get("document_status", ""),
        "application_types": EnrollmentApplication.ApplicationType.choices,
        "document_statuses": StudentDocument.Status.choices,
        "classes": class_choices(raw=True),
        "clear_query": build_querystring(
            {key: value for key, value in list_query_values.items() if key != "q"}
        ),
        "list_query": build_querystring(list_query_values),
        "list_hidden_fields": [
            {"name": key, "value": value} for key, value in list_query_values.items() if key != "q"
        ],
        "list_filters_template": "enrollments/partials/application_list_filters.html",
        "list_table_template": "enrollments/partials/applications_table.html",
        "pagination_target": "#applications-table",
        "pagination_swap": "outerHTML",
        "pagination_push_url": True,
        "is_htmx": is_htmx,
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Matrículas", "url": None},
        ],
    }
    if is_htmx:
        return render(request, "partials/tabbed_list_card.html", context)
    return render(request, "enrollments/application_list.html", context)


@login_required
@access_policy("enrollments", CREATE)
def enrollment_application_create(request):
    """Cria solicitação para aluno já cadastrado."""
    selected_student_id = (
        request.POST.get("student_id")
        or request.GET.get("student")
        or request.GET.get("student_id")
    )
    student_search = request.POST.get("student_search", "").strip()
    kwargs = application_form_choices(selected_student_id, student_search=student_search)
    form_action = request.POST.get("form_action", "")
    is_refresh = request.method == "POST" and form_action in {"search", "refresh_context"}
    is_context_refresh = (
        is_refresh
        and form_action == "refresh_context"
        and request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-Target") == "application-context-fields"
    )
    application_type = (
        request.POST.get("application_type")
        or request.GET.get("application_type")
        or ("NEW" if request.GET.get("class") else "")
    )
    initial = {
        "target_class_id": (
            request.POST.get("target_class_id")
            or request.GET.get("target_class_id")
            or request.GET.get("class", "")
        ),
        "student_id": selected_student_id or "",
        "application_type": application_type,
        "source_enrollment_id": request.POST.get("source_enrollment_id", ""),
        "origin_school": request.POST.get("origin_school", ""),
        "destination_school": request.POST.get("destination_school", ""),
        "priority": request.POST.get("priority", 0),
        "notes": request.POST.get("notes", ""),
    }
    form = EnrollmentApplicationForm(
        None if is_refresh else request.POST or None,
        initial=initial,
        **kwargs,
    )
    if is_context_refresh:
        return render(
            request,
            "enrollments/partials/application_context_fields.html",
            {"form": form, "selected_application_type": application_type},
        )
    if request.method == "POST" and not is_refresh and form.is_valid():
        try:
            application = EnrollmentApplicationService(user=request.user).create_application(
                form.cleaned_data
            )
            messages.success(request, "Solicitação criada com sucesso.")
            return redirect("enrollment_application_detail", pk=application.pk)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except (ObjectNotFoundError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "enrollments/application_form.html",
        {
            "form": form,
            "title": "Nova solicitação de matrícula",
            "student_search": student_search,
            "selected_application_type": application_type,
        },
    )


@login_required
@access_policy("enrollments", CREATE)
def enrollment_student_search(request):
    """Retorna opções HTMX para a busca de aluno, mantendo fallback server-side."""
    from students.selectors import StudentSelector

    result = StudentSelector().list_students(search=request.GET.get("q", "").strip(), page_size=50)
    return render(request, "enrollments/partials/student_options.html", {"students": result.items})


@login_required
@access_policy("enrollments", VIEW)
def enrollment_application_detail(request, pk):
    """Exibe processo, vagas, checklist e histórico em grade 5/7."""
    detail = EnrollmentApplicationSelector().get_application_detail(pk)
    return render(
        request,
        "enrollments/application_detail.html",
        application_detail_context(detail),
    )


@login_required
@access_policy("enrollments", EDIT)
def enrollment_application_correct(request, pk):
    """Edita os campos compatíveis com o tipo usando fallback GET/POST completo."""
    application = EnrollmentApplicationSelector().get_application_by_id(pk)
    choices = application_form_choices(application.student_id)
    form = EnrollmentApplicationCorrectionForm(
        request.POST or None,
        initial={
            "expected_version": application.version,
            "target_class_id": application.target_class_id or "",
            "source_enrollment_id": application.source_enrollment_id or "",
            "origin_school": application.origin_school,
            "destination_school": application.destination_school,
            "priority": application.priority,
            "notes": application.notes,
        },
        class_choices=choices["class_choices"],
        enrollment_choices=choices["enrollment_choices"],
    )
    if request.method == "POST" and form.is_valid():
        try:
            application = EnrollmentApplicationService(user=request.user).correct_application(
                pk,
                form.cleaned_data,
                expected_version=form.cleaned_data["expected_version"],
            )
            messages.success(request, "Solicitação corrigida.")
            return redirect("enrollment_application_detail", pk=application.pk)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except (BusinessRuleViolationError, ObjectNotFoundError) as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "enrollments/application_correction_form.html",
        {"form": form, "application": application, "title": "Corrigir solicitação"},
    )


@login_required
@access_policy("enrollments", EDIT)
def enrollment_application_action(request, pk):
    """Orquestra as ações contextuais da ficha e atualiza somente o card do processo."""
    if request.method != "POST":
        return redirect("enrollment_application_detail", pk=pk)
    service = EnrollmentApplicationService(user=request.user)
    action = request.POST.get("action", "")
    version = parse_optional_int(request.POST.get("expected_version"))
    reason = request.POST.get("reason", "")
    try:
        updated_application = None
        if action == "submit":
            updated_application = service.submit_application(pk, expected_version=version)
        elif action == "approve":
            updated_application = service.approve_application(pk, expected_version=version)
        elif action == "correction":
            updated_application = service.request_correction(pk, reason, expected_version=version)
        elif action == "reject":
            updated_application = service.reject_application(pk, reason, expected_version=version)
        elif action == "finalize":
            updated_application = service.finalize_application(
                pk, expected_version=version, reason=reason
            )
        elif action == "cancel":
            updated_application = service.cancel_application(pk, reason, expected_version=version)
        else:
            raise ValidationError(errors={"action": ["Ação inválida."]})
        if (
            action == "approve"
            and updated_application.status == EnrollmentApplication.Status.WAITLISTED
        ):
            placement = EnrollmentApplicationSelector().get_application_detail(pk)
            messages.warning(
                request,
                "Turma sem vaga. Solicitação incluída na lista de espera "
                f"na posição {placement.waitlist_position} de {placement.waitlist_total}.",
            )
        else:
            messages.success(request, "Solicitação atualizada.")
    except (ValidationError, BusinessRuleViolationError, ObjectNotFoundError) as exc:
        messages.error(request, exc.message)
    if request.headers.get("HX-Request"):
        detail = EnrollmentApplicationSelector().get_application_detail(pk)
        return render(
            request,
            "enrollments/partials/application_process_card.html",
            application_detail_context(detail, htmx_messages=True),
        )
    return redirect("enrollment_application_detail", pk=pk)


@login_required
@access_policy("enrollments", EDIT)
def enrollment_reminder_send(request, pk):
    """Solicita lembretes, publicados no broker somente depois do commit."""
    if request.method == "POST":
        try:
            EnrollmentReminderService(user=request.user).send_reminders(
                pk, expected_version=parse_optional_int(request.POST.get("expected_version"))
            )
            messages.success(request, "Lembretes enfileirados.")
        except (ValidationError, BusinessRuleViolationError, ObjectNotFoundError) as exc:
            messages.error(request, exc.message)
    if request.headers.get("HX-Request"):
        detail = EnrollmentApplicationSelector().get_application_detail(pk)
        return render(
            request,
            "enrollments/partials/application_documents_card.html",
            application_detail_context(detail, htmx_messages=True),
        )
    return redirect("enrollment_application_detail", pk=pk)
