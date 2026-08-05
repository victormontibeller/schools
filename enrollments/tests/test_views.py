"""Integração HTTP e HTMX do workflow de matrículas."""

import datetime as dt

import pytest
from django.urls import reverse


@pytest.fixture()
def records(user):
    from classes.models import Class
    from classes.services import ClassService
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService
    from students.models import Student

    student = Student.objects.create(
        first_name="Iara",
        last_name="Luz",
        birth_date=dt.date(2015, 1, 1),
        enrollment_number="HTTP-1",
        created_by=user,
        updated_by=user,
    )
    class_obj = ClassService(user=user).create_class(
        {
            "name": "HTTP 4A",
            "grade": Class.Grade.ELEMENTARY_4,
            "education_stage": Class.EducationStage.ELEMENTARY_I,
            "academic_year": 2026,
        }
    )
    application = EnrollmentApplicationService(user=user).create_application(
        {
            "student_id": student.pk,
            "target_class_id": class_obj.pk,
            "application_type": EnrollmentApplication.ApplicationType.NEW,
        }
    )
    return student, class_obj, application


@pytest.mark.django_db
def test_list_uses_canonical_shell_and_htmx_returns_fragment(client, user, records):
    client.force_login(user)
    url = reverse("enrollment_application_list")
    full = client.get(url)
    partial = client.get(url, HTTP_HX_REQUEST="true")

    assert full.status_code == 200
    assert b"sm-viewport-card" in full.content
    assert records[2].application_number.encode() in partial.content
    assert b"<html" not in partial.content
    assert b'id="applications-table"' in partial.content
    assert b'aria-label="Etapas da matr\xc3\xadcula"' in partial.content
    assert b'class="nav nav-tabs sm-tabs flex-nowrap overflow-auto"' in partial.content
    assert b'data-sm-list-tabs="applications-table"' in partial.content
    assert b'data-sm-tab-id="encerradas"' in partial.content
    assert b'hx-swap-oob="outerHTML"' in partial.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "request_headers",
    ({}, {"HTTP_HX_REQUEST": "true"}),
    ids=("full_page", "htmx"),
)
def test_list_invalid_tab_falls_back_to_first_accessible_tab(
    client, user, records, request_headers
):
    client.force_login(user)

    response = client.get(
        reverse("enrollment_application_list"),
        {"tab": "etapa-inexistente"},
        **request_headers,
    )

    assert response.status_code == 200
    assert response.context["tab"] == "pre-matriculas"
    assert response.context["list_tabs"][0]["active"] is True
    assert b'aria-current="page">Pr\xc3\xa9-matr\xc3\xadculas ' in response.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "request_headers",
    ({}, {"HTTP_HX_REQUEST": "true"}),
    ids=("full_page", "htmx"),
)
def test_list_invalid_class_id_is_ignored_in_selector_and_rendered_query(
    client, user, records, request_headers
):
    client.force_login(user)

    response = client.get(
        reverse("enrollment_application_list"),
        {"class_id": "uuid-invalido", "q": records[2].application_number},
        **request_headers,
    )

    assert response.status_code == 200
    assert response.context["class_id"] == ""
    assert "class_id=" not in response.context["list_query"]
    assert "class_id=" not in response.context["clear_query"]
    assert records[2].application_number.encode() in response.content


@pytest.mark.django_db
def test_create_derives_class_and_redirects_to_detail(client, user, records):
    from enrollments.models import EnrollmentApplication

    other = records[0]
    records[2].status = EnrollmentApplication.Status.CANCELLED
    records[2].save(update_fields=["status"])
    client.force_login(user)
    response = client.post(
        reverse("enrollment_application_create"),
        {
            "student_id": other.pk,
            "target_class_id": records[1].pk,
            "application_type": "NEW",
            "priority": 0,
            "notes": "",
        },
    )

    assert response.status_code == 302
    assert response.url.startswith("/matriculas/")


@pytest.mark.django_db
def test_create_keeps_selected_student_outside_first_page_and_supports_server_search(
    client, user, records
):
    from students.models import Student

    Student.objects.bulk_create(
        [
            Student(
                first_name=f"Aluno {index:03d}",
                last_name="Primeira página",
                birth_date=dt.date(2015, 2, 1),
                enrollment_number=f"HTTP-PAGE-{index:03d}",
                created_by=user,
                updated_by=user,
            )
            for index in range(101)
        ]
    )
    selected = Student.objects.create(
        first_name="Zulu",
        last_name="Fora da página",
        birth_date=dt.date(2015, 3, 1),
        enrollment_number="HTTP-ZULU-999",
        created_by=user,
        updated_by=user,
    )
    client.force_login(user)
    url = reverse("enrollment_application_create")

    search = client.post(
        url,
        {"form_action": "search", "student_search": "HTTP-ZULU-999"},
    )
    assert search.status_code == 200
    assert str(selected.pk).encode() in search.content
    assert b"Zulu" in search.content

    created = client.post(
        url,
        {
            "student_id": selected.pk,
            "target_class_id": records[1].pk,
            "application_type": "NEW",
            "priority": 0,
            "notes": "",
        },
    )
    assert created.status_code == 302


@pytest.mark.django_db
def test_create_rejects_malformed_student_id_without_http_500(client, user, records):
    client.force_login(user)
    url = reverse("enrollment_application_create")

    assert client.get(url, {"student": "not-a-uuid"}).status_code == 200
    response = client.post(
        url,
        {
            "student_id": "not-a-uuid",
            "target_class_id": records[1].pk,
            "application_type": "NEW",
            "priority": 0,
        },
    )

    assert response.status_code == 200
    assert "student_id" in response.context["form"].errors


@pytest.mark.django_db
def test_action_htmx_replaces_only_process_card(client, user, records):
    client.force_login(user)
    application = records[2]
    response = client.post(
        reverse("enrollment_application_action", args=[application.pk]),
        {"action": "submit", "expected_version": application.version},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"application-process-card" in response.content
    assert "Solicitação atualizada".encode() in response.content
    assert b"<html" not in response.content

    failed = client.post(
        reverse("enrollment_application_action", args=[application.pk]),
        {"action": "submit", "expected_version": application.version},
        HTTP_HX_REQUEST="true",
    )
    assert b"alterado por outra pessoa" in failed.content


@pytest.mark.django_db
@pytest.mark.parametrize("version", [None, "not-a-number", "stale"])
def test_reminder_rejects_invalid_expected_version_without_http_500(client, user, records, version):
    client.force_login(user)
    application = records[2]
    data = {}
    if version == "stale":
        data["expected_version"] = application.version + 1
    elif version is not None:
        data["expected_version"] = version

    response = client.post(
        reverse("enrollment_reminder_send", args=[application.pk]),
        data,
    )

    assert response.status_code == 302
    assert response.url == reverse("enrollment_application_detail", args=[application.pk])


@pytest.mark.django_db
def test_document_action_htmx_replaces_only_checklist_card(client, user, records):
    from enrollments.models import StudentDocument
    from enrollments.services import StudentDocumentService

    document = StudentDocument.objects.create(
        application=records[2],
        requirement_code="physical-proof",
        requirement_label="Comprovante físico",
        is_required=True,
        allows_physical=True,
        created_by=user,
        updated_by=user,
    )
    document = StudentDocumentService(user=user).record_delivery(
        document.pk,
        delivery_method=StudentDocument.DeliveryMethod.PHYSICAL,
        expected_version=document.version,
    )
    client.force_login(user)

    response = client.post(
        reverse("enrollment_document_action", args=[document.pk]),
        {"action": "verify", "expected_version": document.version},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"application-documents-card" in response.content
    assert b"Verificado" in response.content
    assert b"Documento atualizado" in response.content
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_document_waiver_is_denied_at_http_boundary_for_non_admin(client, user, records):
    from django.utils import timezone

    from core.models import Role, RoleModuleAccess
    from enrollments.models import StudentDocument

    document = StudentDocument.objects.create(
        application=records[2],
        requirement_code="admin-waiver",
        requirement_label="Documento dispensável somente pelo Admin",
        is_required=True,
        allows_physical=True,
        created_by=user,
        updated_by=user,
    )
    secretary = Role.objects.get(name=Role.Name.SECRETARY)
    RoleModuleAccess.objects.update_or_create(
        role=secretary,
        module_key="enrollments",
        defaults={
            "can_view": True,
            "can_create": True,
            "can_edit": True,
            "can_deactivate": False,
        },
    )
    RoleModuleAccess.objects.update_or_create(
        role=secretary,
        module_key="document_requirements",
        defaults={
            "can_view": True,
            "can_create": True,
            "can_edit": True,
            "can_deactivate": True,
        },
    )
    user.role = secretary
    user.is_superuser = False
    user.access_mode = "DEMO"
    user.email_verified_at = timezone.now()
    user.save(update_fields=["role", "is_superuser", "access_mode", "email_verified_at"])
    client.force_login(user)

    detail = client.get(reverse("enrollment_application_detail", args=[records[2].pk]))
    response = client.post(
        reverse("enrollment_document_action", args=[document.pk]),
        {
            "action": "waive",
            "reason": "Tentativa sem privilégio administrativo",
            "expected_version": document.version,
        },
    )

    assert detail.status_code == 200
    assert b"Dispensar" not in detail.content
    assert response.status_code == 403
    document.refresh_from_db()
    assert document.status == StudentDocument.Status.PENDING


@pytest.mark.django_db
def test_detail_exposes_transfer_context_fields(client, user, records):
    client.force_login(user)
    response = client.get(reverse("enrollment_application_detail", args=[records[2].pk]))

    assert response.status_code == 200
    assert "Matrícula de origem".encode() in response.content
    assert b"Escola de origem" in response.content
    assert b"Escola de destino" in response.content
    assert "Observações".encode() in response.content


@pytest.mark.django_db
def test_routes_require_authentication(client, records):
    response = client.get(reverse("enrollment_application_detail", args=[records[2].pk]))
    assert response.status_code == 302


@pytest.mark.django_db
def test_correction_has_get_post_fallback_and_expected_version(client, user, records):
    client.force_login(user)
    application = records[2]
    url = reverse("enrollment_application_correct", args=[application.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert b"expected_version" in response.content

    response = client.post(
        url,
        {
            "expected_version": application.version,
            "target_class_id": records[1].pk,
            "source_enrollment_id": "",
            "origin_school": "",
            "destination_school": "",
            "priority": 2,
            "notes": "Ajuste administrativo",
        },
    )
    assert response.status_code == 302
    application.refresh_from_db()
    assert application.priority == 2
    assert application.notes == "Ajuste administrativo"


@pytest.mark.django_db
def test_list_preserves_filters_in_tabs_and_htmx_fragment(client, user, records):
    client.force_login(user)
    params = {
        "q": records[2].application_number,
        "academic_year": 2026,
        "class_id": records[1].pk,
        "application_type": "NEW",
        "document_status": "PENDING",
        "page": 3,
    }
    response = client.get(reverse("enrollment_application_list"), params)
    assert response.status_code == 200
    assert b"academic_year=2026" in response.content
    clear_link = (
        response.content.decode()
        .split('aria-label="Limpar busca"', maxsplit=1)[0]
        .rsplit("<a", maxsplit=1)[1]
    )
    assert "q=" not in clear_link
    assert "academic_year=2026" in clear_link
    assert f"class_id={records[1].pk}" in clear_link
    corrections_tab = next(
        item for item in response.context["list_tabs"] if item["id"] == "correcoes"
    )
    assert "q=" in corrections_tab["query"]
    assert "academic_year=2026" in corrections_tab["query"]
    assert f"class_id={records[1].pk}" in corrections_tab["query"]
    assert "application_type=NEW" in corrections_tab["query"]
    assert "document_status=PENDING" in corrections_tab["query"]
    assert "page=" not in corrections_tab["query"]
    fragment = client.get(reverse("enrollment_application_list"), params, HTTP_HX_REQUEST="true")
    assert fragment.status_code == 200
    assert b"<html" not in fragment.content
    assert b'name="q"' in fragment.content
    assert b'value="PENDING"' in fragment.content
    assert b'hx-push-url="true"' in fragment.content


@pytest.mark.django_db
def test_document_upload_and_private_download_headers(client, user, records):
    from base import context
    from base.tests.images import png_upload
    from enrollments.models import StudentDocument

    document = StudentDocument.objects.create(
        application=records[2],
        requirement_code="identity",
        requirement_label="Identidade",
        is_required=True,
        created_by=user,
        updated_by=user,
    )
    client.force_login(user)
    token = context.current_tenant.set("tenant_upload")
    try:
        response = client.post(
            reverse("enrollment_document_delivery", args=[document.pk]),
            {
                "expected_version": document.version,
                "delivery_method": "DIGITAL",
                "file": png_upload("identity.png"),
            },
        )
        assert response.status_code == 302
        document.refresh_from_db()
        assert "/documents/enrollments/" in document.file.name
        assert "identity" not in document.file.name
        download = client.get(reverse("enrollment_document_download", args=[document.pk]))
        assert download.status_code == 200
        assert download["Cache-Control"] == "private, no-store"
        assert download["X-Content-Type-Options"] == "nosniff"
        assert download["Content-Disposition"].startswith("attachment;")
        download.close()
    finally:
        context.current_tenant.reset(token)
        document.file.delete(save=False)


@pytest.mark.django_db
def test_view_only_role_cannot_open_creation_helpers_or_confirm_batch(client, user, records):
    from django.utils import timezone

    from base.exceptions import PermissionDeniedError
    from core.models import Role, RoleModuleAccess
    from enrollments.services import ReenrollmentService

    role = Role.objects.get(name=Role.Name.COORDINATOR)
    RoleModuleAccess.objects.update_or_create(
        role=role,
        module_key="enrollments",
        defaults={
            "can_view": True,
            "can_create": False,
            "can_edit": False,
            "can_deactivate": False,
        },
    )
    RoleModuleAccess.objects.update_or_create(
        role=role,
        module_key="reenrollment",
        defaults={
            "can_view": True,
            "can_create": False,
            "can_edit": False,
            "can_deactivate": False,
        },
    )
    RoleModuleAccess.objects.update_or_create(
        role=role,
        module_key="document_requirements",
        defaults={
            "can_view": True,
            "can_create": False,
            "can_edit": False,
            "can_deactivate": False,
        },
    )
    user.role = role
    user.is_superuser = False
    user.access_mode = "DEMO"
    user.email_verified_at = timezone.now()
    user.save(update_fields=["role", "is_superuser", "access_mode", "email_verified_at"])
    client.force_login(user)

    listing = client.get(reverse("enrollment_application_list"))
    assert listing.status_code == 200
    assert b"Configurar documentos" not in listing.content
    assert client.get(reverse("enrollment_application_create")).status_code == 403
    assert client.get(reverse("enrollment_student_search")).status_code == 403
    assert client.get(reverse("reenrollment_batch")).status_code == 200
    assert client.post(reverse("reenrollment_batch")).status_code == 405
    assert client.post(reverse("reenrollment_batch_confirm"), {}).status_code == 403
    requirements = client.get(reverse("document_requirement_list"))
    assert requirements.status_code == 200
    assert b"NOVO" not in requirements.content
    assert client.get(reverse("document_requirement_create")).status_code == 403
    with pytest.raises(PermissionDeniedError):
        ReenrollmentService(user=user).confirm_batch([])


@pytest.mark.django_db
def test_document_requirement_form_uses_canonical_structure_and_http_fallback(client, user):
    client.force_login(user)
    list_url = reverse("document_requirement_list")
    create_url = reverse("document_requirement_create")

    response = client.get(create_url)
    html = response.content.decode()
    rendered_templates = {
        template.name for template in response.templates if getattr(template, "name", None)
    }

    assert response.status_code == 200
    assert "entity_form_base.html" in rendered_templates
    assert "partials/form_field.html" in rendered_templates
    assert '<div class="row g-3 align-items-start">' in html
    assert '<div class="col-12 col-xl-5">' in html
    assert '<form id="primary-form" method="post"' in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert f'href="{list_url}" class="btn btn-sm btn-outline-secondary"' in html
    assert 'type="hidden" name="expected_version"' in html
    assert html.count('<div class="col-12 col-md-6">') == 2
    assert html.index('name="application_type"') < html.index('name="code"')
    assert html.index('name="code"') < html.index('name="label"')
    assert html.index('name="label"') < html.index('name="display_order"')
    assert html.index('name="display_order"') < html.index('name="is_required"')
    assert html.index('name="is_required"') < html.index('name="allows_physical"')


@pytest.mark.django_db
def test_admin_configures_future_document_requirements_with_http_fallback(client, user):
    from enrollments.models import DocumentRequirement

    client.force_login(user)
    list_url = reverse("document_requirement_list")
    assert client.get(list_url).status_code == 200

    create = client.post(
        reverse("document_requirement_create"),
        {
            "expected_version": 0,
            "application_type": "NEW",
            "code": "proof-of-address",
            "label": "Comprovante de endereço",
            "is_required": "on",
            "allows_physical": "on",
            "display_order": 10,
        },
    )
    assert create.status_code == 302
    requirement = DocumentRequirement.objects.get(code="proof-of-address")

    edit_url = reverse("document_requirement_edit", args=[requirement.pk])
    assert b"expected_version" in client.get(edit_url).content
    edit = client.post(
        edit_url,
        {
            "expected_version": requirement.version,
            "application_type": "NEW",
            "code": "proof-of-address",
            "label": "Comprovante residencial",
            "is_required": "on",
            "display_order": 20,
        },
    )
    assert edit.status_code == 302
    requirement.refresh_from_db()
    assert requirement.label == "Comprovante residencial"
    assert requirement.allows_physical is False

    fragment = client.get(list_url, HTTP_HX_REQUEST="true")
    assert fragment.status_code == 200
    assert b"Comprovante residencial" in fragment.content
    assert b"<html" not in fragment.content

    deactivate = client.post(
        reverse("document_requirement_deactivate", args=[requirement.pk]),
        {"expected_version": requirement.version},
    )
    assert deactivate.status_code == 302
    assert DocumentRequirement.all_objects.get(pk=requirement.pk).is_active is False


@pytest.mark.django_db
def test_document_requirement_http_actions_are_independent(client, user):
    from django.utils import timezone

    from core.models import Role, RoleModuleAccess
    from enrollments.models import DocumentRequirement, EnrollmentApplication
    from enrollments.services import StudentDocumentService

    requirement = StudentDocumentService(user=user).create_requirement(
        {
            "application_type": EnrollmentApplication.ApplicationType.NEW,
            "code": "independent-http",
            "label": "Documento independente",
        }
    )
    coordinator = Role.objects.get(name=Role.Name.COORDINATOR)
    RoleModuleAccess.objects.update_or_create(
        role=coordinator,
        module_key="enrollments",
        defaults={
            "can_view": False,
            "can_create": False,
            "can_edit": False,
            "can_deactivate": False,
        },
    )
    access, _ = RoleModuleAccess.objects.update_or_create(
        role=coordinator,
        module_key="document_requirements",
        defaults={
            "can_view": True,
            "can_create": False,
            "can_edit": False,
            "can_deactivate": False,
        },
    )
    user.role = coordinator
    user.is_superuser = False
    user.access_mode = "DEMO"
    user.email_verified_at = timezone.now()
    user.save(update_fields=["role", "is_superuser", "access_mode", "email_verified_at"])
    client.force_login(user)

    listing = client.get(reverse("document_requirement_list"))
    assert listing.status_code == 200
    assert f'href="{reverse("enrollment_application_list")}"' not in listing.content.decode()
    assert (
        reverse("document_requirement_edit", args=[requirement.pk]) not in listing.content.decode()
    )
    assert b"Desativar" not in listing.content
    assert client.get(reverse("document_requirement_create")).status_code == 403
    assert (
        client.get(reverse("document_requirement_edit", args=[requirement.pk])).status_code == 403
    )
    assert (
        client.post(
            reverse("document_requirement_deactivate", args=[requirement.pk]),
            {"expected_version": requirement.version},
        ).status_code
        == 403
    )

    access.can_create = True
    access.save(update_fields=["can_create"])
    assert client.get(reverse("document_requirement_create")).status_code == 200

    access.can_edit = True
    access.save(update_fields=["can_edit"])
    assert (
        client.get(reverse("document_requirement_edit", args=[requirement.pk])).status_code == 200
    )

    access.can_deactivate = True
    access.save(update_fields=["can_deactivate"])
    response = client.post(
        reverse("document_requirement_deactivate", args=[requirement.pk]),
        {"expected_version": requirement.version},
    )
    assert response.status_code == 302
    assert DocumentRequirement.all_objects.get(pk=requirement.pk).is_active is False


@pytest.mark.django_db
def test_reenrollment_preselects_only_unique_pedagogical_destination(client, user, records):
    from django.utils import timezone

    from classes.models import Class
    from classes.services import ClassService
    from core.models import Role, RoleModuleAccess
    from enrollments.services import EnrollmentApplicationService

    application = records[2]
    service = EnrollmentApplicationService(user=user)
    application = service.submit_application(application.pk, expected_version=application.version)
    application = service.approve_application(application.pk, expected_version=application.version)
    source = service.finalize_application(
        application.pk, expected_version=application.version
    ).result_enrollment
    suggested = ClassService(user=user).create_class(
        {
            "name": "HTTP 5A sugerida",
            "grade": Class.Grade.ELEMENTARY_5,
            "education_stage": Class.EducationStage.ELEMENTARY_I,
            "academic_year": 2027,
            "shift": records[1].shift,
        }
    )
    repetition = ClassService(user=user).create_class(
        {
            "name": "HTTP 4A repetência",
            "grade": Class.Grade.ELEMENTARY_4,
            "education_stage": Class.EducationStage.ELEMENTARY_I,
            "academic_year": 2027,
            "shift": records[1].shift,
        }
    )
    exceptional = ClassService(user=user).create_class(
        {
            "name": "HTTP 7A excepcional",
            "grade": Class.Grade.ELEMENTARY_7,
            "education_stage": Class.EducationStage.ELEMENTARY_II,
            "academic_year": 2027,
            "shift": Class.Shift.AFTERNOON,
        }
    )
    coordinator = Role.objects.get(name=Role.Name.COORDINATOR)
    RoleModuleAccess.objects.update_or_create(
        role=coordinator,
        module_key="enrollments",
        defaults={
            "can_view": False,
            "can_create": False,
            "can_edit": False,
            "can_deactivate": False,
        },
    )
    RoleModuleAccess.objects.update_or_create(
        role=coordinator,
        module_key="students",
        defaults={
            "can_view": False,
            "can_create": False,
            "can_edit": False,
            "can_deactivate": False,
        },
    )
    RoleModuleAccess.objects.update_or_create(
        role=coordinator,
        module_key="reenrollment",
        defaults={
            "can_view": True,
            "can_create": True,
            "can_edit": False,
            "can_deactivate": False,
        },
    )
    user.role = coordinator
    user.is_superuser = False
    user.access_mode = "DEMO"
    user.email_verified_at = timezone.now()
    user.save(update_fields=["role", "is_superuser", "access_mode", "email_verified_at"])
    client.force_login(user)

    response = client.get(
        reverse("reenrollment_batch"),
        {"source_class_id": records[1].pk},
    )
    html = response.content.decode()

    assert response.status_code == 200
    assert f'action="{reverse("reenrollment_batch_confirm")}"' in html
    assert f'value="{suggested.pk}" selected' in html
    assert f'value="{repetition.pk}" selected' not in html
    assert str(exceptional.pk) in html
    assert "repetência (justifique)" in html
    assert "exceção (justifique)" in html
    assert f'href="{reverse("enrollment_application_list")}"' not in html
    assert reverse("student_profile", args=[source.student_id]) not in html

    assert client.post(reverse("reenrollment_batch"), {}).status_code == 405
    confirmed = client.post(
        reverse("reenrollment_batch_confirm"),
        {
            "source_class_id": records[1].pk,
            "source_enrollment_ids": [source.pk],
            f"target_{source.pk}": suggested.pk,
            f"version_{source.pk}": source.version,
            f"reason_{source.pk}": "",
        },
    )
    assert confirmed.status_code == 302
    assert confirmed.url == reverse("reenrollment_batch")
    assert client.get(confirmed.url).status_code == 200
