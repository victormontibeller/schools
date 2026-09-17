"""Cobertura do workflow canônico de solicitações e documentos."""

import datetime as dt
import logging
from unittest.mock import Mock, call

import pytest

from base.exceptions import (
    BusinessRuleViolationError,
    PermissionDeniedError,
    ValidationError,
)


@pytest.fixture()
def student(user):
    from students.models import Student

    return Student.objects.create(
        first_name="Ana",
        last_name="Silva",
        birth_date=dt.date(2014, 5, 1),
        enrollment_number="ALU-WORKFLOW-1",
        created_by=user,
        updated_by=user,
    )


@pytest.fixture()
def class_obj(user):
    from classes.models import Class
    from classes.services import ClassService

    return ClassService(user=user).create_class(
        {
            "name": "5A Workflow",
            "grade": Class.Grade.ELEMENTARY_5,
            "education_stage": Class.EducationStage.ELEMENTARY_I,
            "academic_year": 2026,
            "shift": Class.Shift.MORNING,
            "max_students": 2,
        }
    )


def _create_application(user, student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService

    return EnrollmentApplicationService(user=user).create_application(
        {
            "student_id": student.pk,
            "target_class_id": class_obj.pk,
            "application_type": EnrollmentApplication.ApplicationType.NEW,
        }
    )


def _add_pending_document(user, application):
    from enrollments.models import StudentDocument

    return StudentDocument.objects.create(
        application=application,
        requirement_code="pending",
        requirement_label="Pendente",
        is_required=True,
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
def test_demo_seed_enrollment_uses_canonical_workflow_and_is_idempotent(
    user,
    student,
    class_obj,
):
    from enrollments.demo_seed import ensure_demo_enrollment
    from enrollments.models import EnrollmentApplication

    enrollment = ensure_demo_enrollment(user, student, class_obj)
    repeated = ensure_demo_enrollment(user, student, class_obj)

    assert repeated.pk == enrollment.pk
    application = EnrollmentApplication.objects.get(result_enrollment=enrollment)
    assert application.status == EnrollmentApplication.Status.ENROLLED
    assert application.application_number.startswith(f"MAT-{class_obj.academic_year}-")


@pytest.mark.django_db
def test_demo_seed_enrollment_rejects_missing_actor(student, class_obj):
    from enrollments.demo_seed import ensure_demo_enrollment

    with pytest.raises(PermissionDeniedError):
        ensure_demo_enrollment(None, student, class_obj)


@pytest.mark.django_db
def test_create_derives_year_protocol_and_history(user, student, class_obj):
    application = _create_application(user, student, class_obj)
    assert application.academic_year == class_obj.academic_year
    assert application.application_number == "MAT-2026-000001"
    assert application.transitions.get().to_status == "PRE_ENROLLMENT"


@pytest.mark.django_db
def test_create_commands_reject_malformed_expected_version(user, student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService, StudentDocumentService

    with pytest.raises(ValidationError):
        EnrollmentApplicationService(user=user).create_application(
            {
                "student_id": student.pk,
                "target_class_id": class_obj.pk,
                "application_type": EnrollmentApplication.ApplicationType.NEW,
            },
            expected_version="invalid",
        )

    with pytest.raises(ValidationError):
        StudentDocumentService(user=user).create_requirement(
            {
                "application_type": EnrollmentApplication.ApplicationType.NEW,
                "code": "birth-certificate",
                "label": "Certidão",
            },
            expected_version="invalid",
        )


@pytest.mark.django_db
def test_document_requirement_rejects_invalid_configuration_values(user):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import StudentDocumentService

    service = StudentDocumentService(user=user)
    valid = {
        "application_type": EnrollmentApplication.ApplicationType.NEW,
        "code": "proof",
        "label": "Comprovante",
    }

    with pytest.raises(BusinessRuleViolationError):
        service.create_requirement(valid, expected_version=1)
    with pytest.raises(ValidationError):
        service.create_requirement({**valid, "application_type": "UNKNOWN"})
    with pytest.raises(ValidationError):
        service.create_requirement({**valid, "code": "!!!"})
    with pytest.raises(ValidationError):
        service.create_requirement({**valid, "display_order": "invalid"})
    with pytest.raises(ValidationError):
        service.create_requirement({**valid, "display_order": 32768})


@pytest.mark.django_db
def test_create_snapshots_document_requirements(user, student, class_obj):
    from enrollments.models import DocumentRequirement, EnrollmentApplication
    from enrollments.services import StudentDocumentService

    StudentDocumentService(user=user).create_requirement(
        {
            "application_type": EnrollmentApplication.ApplicationType.NEW,
            "code": "certidao",
            "label": "Certidão",
            "is_required": True,
            "allows_physical": True,
        }
    )
    application = _create_application(user, student, class_obj)
    DocumentRequirement.objects.update(label="Nome futuro")

    snapshot = application.documents.get()
    assert snapshot.requirement_label == "Certidão"
    assert snapshot.is_required is True


@pytest.mark.django_db
def test_requirement_changes_affect_only_future_application_snapshots(user, student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import StudentDocumentService
    from students.models import Student

    service = StudentDocumentService(user=user)
    requirement = service.create_requirement(
        {
            "application_type": EnrollmentApplication.ApplicationType.NEW,
            "code": "birth-certificate",
            "label": "Certidão original",
        }
    )
    first = _create_application(user, student, class_obj)
    requirement = service.update_requirement(
        requirement.pk,
        {"label": "Certidão atualizada", "allows_physical": True},
        expected_version=requirement.version,
    )
    second_student = Student.objects.create(
        first_name="Clara",
        last_name="Snapshot",
        birth_date=dt.date(2014, 8, 1),
        enrollment_number="ALU-SNAPSHOT-2",
        created_by=user,
        updated_by=user,
    )
    second = _create_application(user, second_student, class_obj)

    assert first.documents.get().requirement_label == "Certidão original"
    assert second.documents.get().requirement_label == "Certidão atualizada"
    assert second.documents.get().allows_physical is True

    service.deactivate_requirement(
        requirement.pk,
        expected_version=requirement.version,
    )
    third_student = Student.objects.create(
        first_name="Davi",
        last_name="Snapshot",
        birth_date=dt.date(2014, 9, 1),
        enrollment_number="ALU-SNAPSHOT-3",
        created_by=user,
        updated_by=user,
    )
    third = _create_application(user, third_student, class_obj)
    assert not third.documents.exists()


@pytest.mark.django_db
def test_document_requirement_commands_require_each_action_before_writing(user):
    from core.models import Role, RoleModuleAccess
    from enrollments.models import DocumentRequirement, EnrollmentApplication
    from enrollments.services import StudentDocumentService

    requirement = StudentDocumentService(user=user).create_requirement(
        {
            "application_type": EnrollmentApplication.ApplicationType.NEW,
            "code": "service-policy",
            "label": "Política de service",
        }
    )
    coordinator = Role.objects.get(name=Role.Name.COORDINATOR)
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
    user.save(update_fields=["role", "is_superuser", "access_mode"])
    service = StudentDocumentService(user=user)

    initial_count = DocumentRequirement.objects.count()
    with pytest.raises(PermissionDeniedError):
        service.create_requirement(
            {
                "application_type": EnrollmentApplication.ApplicationType.NEW,
                "code": "denied-create",
                "label": "Não deve existir",
            }
        )
    with pytest.raises(PermissionDeniedError):
        service.update_requirement(
            requirement.pk,
            {"label": "Não deve mudar"},
            expected_version=requirement.version,
        )
    with pytest.raises(PermissionDeniedError):
        service.deactivate_requirement(requirement.pk, expected_version=requirement.version)
    requirement.refresh_from_db()
    assert DocumentRequirement.objects.count() == initial_count
    assert requirement.label == "Política de service"
    assert requirement.is_active is True

    access.can_create = True
    access.save(update_fields=["can_create"])
    del user._role_access_cache
    created = service.create_requirement(
        {
            "application_type": EnrollmentApplication.ApplicationType.NEW,
            "code": "allowed-create",
            "label": "Criação permitida",
        }
    )
    access.can_edit = True
    access.save(update_fields=["can_edit"])
    del user._role_access_cache
    created = service.update_requirement(
        created.pk,
        {"label": "Edição permitida"},
        expected_version=created.version,
    )
    access.can_deactivate = True
    access.save(update_fields=["can_deactivate"])
    del user._role_access_cache
    service.deactivate_requirement(created.pk, expected_version=created.version)
    assert DocumentRequirement.all_objects.get(pk=created.pk).is_active is False


@pytest.mark.django_db
def test_document_requirement_create_rolls_back_when_audit_fails(user, monkeypatch):
    from enrollments.models import DocumentRequirement, EnrollmentApplication
    from enrollments.services import StudentDocumentService

    service = StudentDocumentService(user=user)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(service, "_record_audit", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.create_requirement(
            {
                "application_type": EnrollmentApplication.ApplicationType.NEW,
                "code": "audit-rollback",
                "label": "Rollback de auditoria",
            }
        )

    assert not DocumentRequirement.objects.filter(code="audit-rollback").exists()


@pytest.mark.django_db
def test_submit_approve_finalize_creates_single_active_enrollment(user, student, class_obj):
    from classes.models import Enrollment
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    application = _create_application(user, student, class_obj)
    application = service.submit_application(application.pk, expected_version=application.version)
    application = service.approve_application(application.pk, expected_version=application.version)
    application = service.finalize_application(application.pk, expected_version=application.version)

    assert application.status == EnrollmentApplication.Status.ENROLLED
    assert application.result_enrollment.status == Enrollment.Status.ACTIVE
    assert application.result_enrollment.academic_year == 2026


@pytest.mark.django_db
def test_approve_waitlists_when_last_seat_is_reserved(user, student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService
    from students.models import Student

    class_obj.max_students = 1
    class_obj.save(update_fields=["max_students"])
    service = EnrollmentApplicationService(user=user)
    first = _create_application(user, student, class_obj)
    first = service.submit_application(first.pk, expected_version=first.version)
    service.approve_application(first.pk, expected_version=first.version)
    other = Student.objects.create(
        first_name="Bia",
        last_name="Souza",
        birth_date=dt.date(2014, 6, 1),
        enrollment_number="ALU-WORKFLOW-2",
        created_by=user,
        updated_by=user,
    )
    second = _create_application(user, other, class_obj)
    second = service.submit_application(second.pk, expected_version=second.version)
    second = service.approve_application(second.pk, expected_version=second.version)

    assert second.status == EnrollmentApplication.Status.WAITLISTED
    assert second.waitlisted_at is not None
    transition_count = second.transitions.count()
    with pytest.raises(BusinessRuleViolationError):
        service.approve_application(second.pk, expected_version=second.version)
    assert second.transitions.count() == transition_count


@pytest.mark.django_db
def test_waitlist_positions_use_priority_then_age_and_do_not_promote_automatically(
    user, student, class_obj
):
    from enrollments.models import EnrollmentApplication
    from enrollments.selectors import EnrollmentApplicationSelector
    from enrollments.services import EnrollmentApplicationService
    from students.models import Student

    class_obj.max_students = 1
    class_obj.save(update_fields=["max_students"])
    service = EnrollmentApplicationService(user=user)
    reserved = _create_application(user, student, class_obj)
    reserved = service.submit_application(reserved.pk, expected_version=reserved.version)
    reserved = service.approve_application(reserved.pk, expected_version=reserved.version)

    queued = []
    for index, priority in ((2, 2), (3, 10)):
        candidate = Student.objects.create(
            first_name="Fila",
            last_name=str(index),
            birth_date=dt.date(2014, 6, index),
            enrollment_number=f"ALU-WAIT-{index}",
            created_by=user,
            updated_by=user,
        )
        application = service.create_application(
            {
                "student_id": candidate.pk,
                "target_class_id": class_obj.pk,
                "application_type": EnrollmentApplication.ApplicationType.NEW,
                "priority": priority,
            }
        )
        application = service.submit_application(
            application.pk, expected_version=application.version
        )
        queued.append(
            service.approve_application(application.pk, expected_version=application.version)
        )

    selector = EnrollmentApplicationSelector()
    high = selector.get_application_detail(queued[1].pk)
    low = selector.get_application_detail(queued[0].pk)
    listing = selector.list_applications(statuses=[EnrollmentApplication.Status.WAITLISTED])

    assert (high.waitlist_position, high.waitlist_total) == (1, 2)
    assert (low.waitlist_position, low.waitlist_total) == (2, 2)
    assert [item.pk for item in listing.items] == [queued[1].pk, queued[0].pk]
    assert [(item.waitlist_position, item.waitlist_total) for item in listing.items] == [
        (1, 2),
        (2, 2),
    ]

    service.cancel_application(
        reserved.pk,
        "Reserva cancelada.",
        expected_version=reserved.version,
    )
    for application in queued:
        application.refresh_from_db()
        assert application.status == EnrollmentApplication.Status.WAITLISTED


@pytest.mark.django_db
def test_finalize_blocks_unverified_required_document(user, student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService, StudentDocumentService

    StudentDocumentService(user=user).create_requirement(
        {"application_type": "NEW", "code": "id", "label": "Identidade"}
    )
    service = EnrollmentApplicationService(user=user)
    application = _create_application(user, student, class_obj)
    application = service.submit_application(application.pk, expected_version=application.version)
    application = service.approve_application(application.pk, expected_version=application.version)

    with pytest.raises(BusinessRuleViolationError):
        service.finalize_application(application.pk, expected_version=application.version)
    assert application.status == EnrollmentApplication.Status.APPROVED


@pytest.mark.django_db
def test_document_physical_delivery_verify_and_admin_waive(user, student, class_obj):
    from enrollments.models import EnrollmentApplication, StudentDocument
    from enrollments.services import StudentDocumentService

    document_service = StudentDocumentService(user=user)
    document_service.create_requirement(
        {
            "application_type": EnrollmentApplication.ApplicationType.NEW,
            "code": "id",
            "label": "Identidade",
            "allows_physical": True,
        }
    )
    application = _create_application(user, student, class_obj)
    document = application.documents.get()
    document = document_service.record_delivery(
        document.pk,
        delivery_method=StudentDocument.DeliveryMethod.PHYSICAL,
        expected_version=document.version,
    )
    document = document_service.verify_document(document.pk, expected_version=document.version)

    assert document.status == StudentDocument.Status.VERIFIED


@pytest.mark.django_db
def test_reject_and_cancel_require_reason(user, student, class_obj):
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    application = _create_application(user, student, class_obj)
    application = service.submit_application(application.pk, expected_version=application.version)
    with pytest.raises(ValidationError):
        service.reject_application(application.pk, "", expected_version=application.version)


@pytest.mark.django_db
def test_cancel_pre_enrollment_requires_reason_and_releases_student_year(user, student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    application = _create_application(user, student, class_obj)
    with pytest.raises(ValidationError):
        service.cancel_application(application.pk, "", expected_version=application.version)

    cancelled = service.cancel_application(
        application.pk,
        "Solicitação aberta por engano.",
        expected_version=application.version,
    )
    replacement = _create_application(user, student, class_obj)

    assert cancelled.status == EnrollmentApplication.Status.CANCELLED
    assert cancelled.transitions.last().reason == "Solicitação aberta por engano."
    assert replacement.pk != cancelled.pk


@pytest.mark.django_db
def test_cancel_correction_required_checks_expected_version(user, student, class_obj):
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    application = _create_application(user, student, class_obj)
    application = service.submit_application(application.pk, expected_version=application.version)
    application = service.request_correction(
        application.pk,
        "Corrigir dados do processo.",
        expected_version=application.version,
    )

    with pytest.raises(BusinessRuleViolationError):
        service.cancel_application(
            application.pk,
            "Cancelamento solicitado.",
            expected_version=application.version - 1,
        )

    cancelled = service.cancel_application(
        application.pk,
        "Cancelamento solicitado.",
        expected_version=application.version,
    )
    assert cancelled.status == "CANCELLED"


@pytest.mark.django_db
def test_expected_version_conflict_rolls_back_transition(user, student, class_obj):
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    application = _create_application(user, student, class_obj)
    service.submit_application(application.pk, expected_version=application.version)
    with pytest.raises(BusinessRuleViolationError):
        service.submit_application(application.pk, expected_version=application.version)
    assert application.transitions.count() == 2


@pytest.mark.django_db
def test_correct_application_updates_mutable_fields_with_same_derived_year(
    user, student, class_obj
):
    from classes.models import Class
    from classes.services import ClassService
    from enrollments.services import EnrollmentApplicationService

    target = ClassService(user=user).create_class(
        {
            "name": "5B Correção",
            "grade": Class.Grade.ELEMENTARY_5,
            "education_stage": Class.EducationStage.ELEMENTARY_I,
            "academic_year": class_obj.academic_year,
            "shift": class_obj.shift,
        }
    )
    service = EnrollmentApplicationService(user=user)
    application = _create_application(user, student, class_obj)

    corrected = service.correct_application(
        application.pk,
        {
            "target_class_id": target.pk,
            "source_enrollment_id": "",
            "origin_school": "",
            "destination_school": "",
            "priority": 7,
            "notes": "Correção administrativa",
        },
        expected_version=application.version,
    )

    assert corrected.target_class_id == target.pk
    assert corrected.academic_year == application.academic_year
    assert corrected.priority == 7
    assert corrected.notes == "Correção administrativa"


@pytest.mark.django_db
def test_cancel_enrolled_synchronizes_academic_enrollment(user, student, class_obj):
    from classes.models import Enrollment
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    application = _create_application(user, student, class_obj)
    application = service.submit_application(application.pk, expected_version=application.version)
    application = service.approve_application(application.pk, expected_version=application.version)
    application = service.finalize_application(application.pk, expected_version=application.version)
    application = service.cancel_application(
        application.pk, "Desistência", expected_version=application.version
    )
    application.result_enrollment.refresh_from_db()

    assert application.status == EnrollmentApplication.Status.CANCELLED
    assert application.result_enrollment.status == Enrollment.Status.CANCELLED


@pytest.mark.django_db
def test_user_command_denies_missing_actor(student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import (
        EnrollmentApplicationService,
        ReenrollmentService,
        StudentDocumentService,
    )

    with pytest.raises(PermissionDeniedError):
        EnrollmentApplicationService(user=None).create_application(
            {
                "student_id": student.pk,
                "target_class_id": class_obj.pk,
                "application_type": EnrollmentApplication.ApplicationType.NEW,
            }
        )
    applications = EnrollmentApplicationService(user=None)
    denied_application_commands = (
        lambda: applications.correct_application(student.pk, {}, expected_version=0),
        lambda: applications.submit_application(student.pk, expected_version=0),
        lambda: applications.approve_application(student.pk, expected_version=0),
        lambda: applications.request_correction(student.pk, "Motivo", expected_version=0),
        lambda: applications.reject_application(student.pk, "Motivo", expected_version=0),
        lambda: applications.finalize_application(student.pk, expected_version=0),
        lambda: applications.cancel_application(student.pk, "Motivo", expected_version=0),
    )
    for command in denied_application_commands:
        with pytest.raises(PermissionDeniedError):
            command()
    with pytest.raises(PermissionDeniedError):
        ReenrollmentService(user=None).confirm_batch([])
    documents = StudentDocumentService(user=None)
    with pytest.raises(PermissionDeniedError):
        documents.create_requirement({})
    with pytest.raises(PermissionDeniedError):
        documents.update_requirement(student.pk, {}, expected_version=0)
    with pytest.raises(PermissionDeniedError):
        documents.deactivate_requirement(student.pk, expected_version=0)
    with pytest.raises(PermissionDeniedError):
        documents.waive_document(student.pk, "Motivo", expected_version=0)
    denied_document_commands = (
        lambda: documents.record_delivery(
            student.pk, delivery_method="PHYSICAL", expected_version=0
        ),
        lambda: documents.verify_document(student.pk, expected_version=0),
        lambda: documents.reject_document(student.pk, "Motivo", expected_version=0),
    )
    for command in denied_document_commands:
        with pytest.raises(PermissionDeniedError):
            command()


@pytest.mark.django_db
def test_internal_transfer_closes_origin_and_marks_original_application(user, student, class_obj):
    from classes.models import Class, Enrollment
    from classes.services import ClassService
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    original = _create_application(user, student, class_obj)
    original = service.submit_application(original.pk, expected_version=original.version)
    original = service.approve_application(original.pk, expected_version=original.version)
    original = service.finalize_application(original.pk, expected_version=original.version)
    target = ClassService(user=user).create_class(
        {
            "name": "5B Workflow",
            "grade": Class.Grade.ELEMENTARY_5,
            "education_stage": Class.EducationStage.ELEMENTARY_I,
            "academic_year": 2026,
        }
    )
    transfer = service.create_application(
        {
            "student_id": student.pk,
            "source_enrollment_id": original.result_enrollment_id,
            "target_class_id": target.pk,
            "application_type": EnrollmentApplication.ApplicationType.INTERNAL_TRANSFER,
        }
    )
    transfer = service.submit_application(transfer.pk, expected_version=transfer.version)
    transfer = service.approve_application(transfer.pk, expected_version=transfer.version)
    with pytest.raises(ValidationError):
        service.finalize_application(transfer.pk, expected_version=transfer.version)
    transfer = service.finalize_application(
        transfer.pk,
        expected_version=transfer.version,
        reason="Mudança de turma autorizada.",
    )
    original.refresh_from_db()
    original.result_enrollment.refresh_from_db()

    assert transfer.status == EnrollmentApplication.Status.TRANSFERRED
    assert transfer.result_enrollment.status == Enrollment.Status.ACTIVE
    assert original.status == EnrollmentApplication.Status.TRANSFERRED
    assert original.result_enrollment.status == Enrollment.Status.TRANSFERRED
    assert original.result_enrollment.cancel_reason == "Mudança de turma autorizada."
    assert transfer.transitions.last().reason == "Mudança de turma autorizada."


@pytest.mark.django_db
def test_outbound_transfer_requires_destination_and_does_not_create_result(
    user, student, class_obj
):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    original = _create_application(user, student, class_obj)
    original = service.submit_application(original.pk, expected_version=original.version)
    original = service.approve_application(original.pk, expected_version=original.version)
    original = service.finalize_application(original.pk, expected_version=original.version)
    with pytest.raises(ValidationError):
        service.create_application(
            {
                "student_id": student.pk,
                "source_enrollment_id": original.result_enrollment_id,
                "application_type": EnrollmentApplication.ApplicationType.OUTBOUND_TRANSFER,
            }
        )
    transfer = service.create_application(
        {
            "student_id": student.pk,
            "source_enrollment_id": original.result_enrollment_id,
            "application_type": EnrollmentApplication.ApplicationType.OUTBOUND_TRANSFER,
            "destination_school": "Escola de destino",
        }
    )
    transfer = service.submit_application(transfer.pk, expected_version=transfer.version)
    transfer = service.approve_application(transfer.pk, expected_version=transfer.version)
    transfer = service.finalize_application(
        transfer.pk,
        expected_version=transfer.version,
        reason="Transferência solicitada pelo responsável.",
    )

    assert transfer.status == EnrollmentApplication.Status.TRANSFERRED
    assert transfer.result_enrollment_id is None


@pytest.mark.django_db
def test_reenrollment_rejects_target_outside_next_academic_year(user, student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    original = _create_application(user, student, class_obj)
    original = service.submit_application(original.pk, expected_version=original.version)
    original = service.approve_application(original.pk, expected_version=original.version)
    original = service.finalize_application(original.pk, expected_version=original.version)

    with pytest.raises(ValidationError):
        service.create_application(
            {
                "student_id": student.pk,
                "source_enrollment_id": original.result_enrollment_id,
                "target_class_id": class_obj.pk,
                "application_type": EnrollmentApplication.ApplicationType.REENROLLMENT,
            }
        )


@pytest.mark.django_db
def test_audit_failure_rolls_back_state_transition(user, student, class_obj, monkeypatch):
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    application = _create_application(user, student, class_obj)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(service, "_record_audit", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.submit_application(application.pk, expected_version=application.version)
    application.refresh_from_db()

    assert application.status == "PRE_ENROLLMENT"
    assert application.transitions.count() == 1


@pytest.mark.django_db
def test_enrollment_audits_include_redacted_old_and_new_snapshots(user, student, class_obj):
    from audit.models import AuditLog
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService, StudentDocumentService

    service = EnrollmentApplicationService(user=user)
    application = _create_application(user, student, class_obj)
    service.submit_application(application.pk, expected_version=application.version)

    transition_audit = AuditLog.objects.filter(
        model_name="EnrollmentApplication",
        object_id=str(application.pk),
        operation=AuditLog.Operation.UPDATE,
    ).latest("created_at")
    assert transition_audit.old_values["status"] == "PRE_ENROLLMENT"
    assert transition_audit.new_values["status"] == "UNDER_REVIEW"
    assert transition_audit.old_values["notes"] == "[REDACTED]"
    assert transition_audit.new_values["notes"] == "[REDACTED]"

    requirement = StudentDocumentService(user=user).create_requirement(
        {
            "application_type": EnrollmentApplication.ApplicationType.NEW,
            "code": "audit-delete",
            "label": "Documento auditado",
        }
    )
    StudentDocumentService(user=user).deactivate_requirement(
        requirement.pk, expected_version=requirement.version
    )
    delete_audit = AuditLog.objects.get(
        model_name="DocumentRequirement",
        object_id=str(requirement.pk),
        operation=AuditLog.Operation.DELETE,
    )
    assert delete_audit.old_values["is_active"] is True
    assert delete_audit.new_values["is_active"] is False
    assert delete_audit.new_values["deleted_at"] is not None


@pytest.mark.django_db
def test_inbound_transfer_requires_origin_and_creates_active_enrollment(user, student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    data = {
        "student_id": student.pk,
        "target_class_id": class_obj.pk,
        "application_type": EnrollmentApplication.ApplicationType.INBOUND_TRANSFER,
    }
    with pytest.raises(ValidationError):
        service.create_application(data)
    application = service.create_application({**data, "origin_school": "Escola de origem"})
    application = service.submit_application(application.pk, expected_version=application.version)
    application = service.approve_application(application.pk, expected_version=application.version)
    application = service.finalize_application(
        application.pk,
        expected_version=application.version,
        reason="Ingresso por transferência recebido.",
    )

    assert application.status == EnrollmentApplication.Status.ENROLLED
    assert application.result_enrollment.academic_year == class_obj.academic_year


@pytest.mark.django_db
def test_reenrollment_batch_uses_source_version_and_next_year(user, student, class_obj):
    from classes.models import Class
    from classes.services import ClassService
    from core.models import CustomUser, Role, RoleModuleAccess
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService, ReenrollmentService

    application_service = EnrollmentApplicationService(user=user)
    original = _create_application(user, student, class_obj)
    original = application_service.submit_application(
        original.pk, expected_version=original.version
    )
    original = application_service.approve_application(
        original.pk, expected_version=original.version
    )
    original = application_service.finalize_application(
        original.pk, expected_version=original.version
    )
    target = ClassService(user=user).create_class(
        {
            "name": "6A Workflow",
            "grade": Class.Grade.ELEMENTARY_6,
            "education_stage": Class.EducationStage.ELEMENTARY_II,
            "academic_year": 2027,
        }
    )
    coordinator_role = Role.objects.get(name=Role.Name.COORDINATOR)
    RoleModuleAccess.objects.filter(role=coordinator_role, module_key="enrollments").update(
        can_view=True,
        can_create=False,
        can_edit=False,
        can_deactivate=False,
    )
    RoleModuleAccess.objects.filter(role=coordinator_role, module_key="reenrollment").update(
        can_view=True,
        can_create=True,
        can_edit=False,
        can_deactivate=False,
    )
    coordinator = CustomUser.objects.create_user(
        email="coordinator-reenrollment@test.com",
        password="Senha123",
        role=coordinator_role,
        access_mode="DEMO",
    )
    created = ReenrollmentService(user=coordinator).confirm_batch(
        [
            {
                "source_enrollment_id": original.result_enrollment_id,
                "target_class_id": target.pk,
                "expected_version": original.result_enrollment.version,
                "exception_reason": "",
            }
        ]
    )

    assert len(created) == 1
    assert created[0].application_type == EnrollmentApplication.ApplicationType.REENROLLMENT
    assert created[0].academic_year == 2027
    reenrollment = application_service.submit_application(
        created[0].pk, expected_version=created[0].version
    )
    reenrollment = application_service.approve_application(
        reenrollment.pk, expected_version=reenrollment.version
    )
    reenrollment = application_service.finalize_application(
        reenrollment.pk, expected_version=reenrollment.version
    )
    original.refresh_from_db()
    original.result_enrollment.refresh_from_db()
    assert original.status == EnrollmentApplication.Status.ENROLLED
    assert original.result_enrollment.status == "ACTIVE"
    assert reenrollment.status == EnrollmentApplication.Status.ENROLLED


@pytest.mark.django_db
def test_reenrollment_repetition_requires_and_preserves_exception_reason(user, student, class_obj):
    from classes.models import Class
    from classes.services import ClassService
    from enrollments.services import EnrollmentApplicationService, ReenrollmentService

    application_service = EnrollmentApplicationService(user=user)
    original = _create_application(user, student, class_obj)
    original = application_service.submit_application(
        original.pk, expected_version=original.version
    )
    original = application_service.approve_application(
        original.pk, expected_version=original.version
    )
    source = application_service.finalize_application(
        original.pk, expected_version=original.version
    ).result_enrollment
    repetition_class = ClassService(user=user).create_class(
        {
            "name": "5A Repetência",
            "grade": Class.Grade.ELEMENTARY_5,
            "education_stage": Class.EducationStage.ELEMENTARY_I,
            "academic_year": 2027,
            "shift": class_obj.shift,
        }
    )
    mapping = {
        "source_enrollment_id": source.pk,
        "target_class_id": repetition_class.pk,
        "expected_version": source.version,
    }

    with pytest.raises(ValidationError):
        ReenrollmentService(user=user).confirm_batch([mapping])

    created = ReenrollmentService(user=user).confirm_batch(
        [{**mapping, "exception_reason": "Repetência deliberada pelo conselho."}]
    )
    assert created[0].notes == "Repetência deliberada pelo conselho."


@pytest.mark.django_db
def test_enrolled_cancellation_rejects_reason_longer_than_academic_field(user, student, class_obj):
    from classes.models import Enrollment
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=user)
    application = _create_application(user, student, class_obj)
    application = service.submit_application(application.pk, expected_version=application.version)
    application = service.approve_application(application.pk, expected_version=application.version)
    application = service.finalize_application(application.pk, expected_version=application.version)

    with pytest.raises(ValidationError):
        service.cancel_application(
            application.pk,
            "x" * 201,
            expected_version=application.version,
        )

    application.refresh_from_db()
    application.result_enrollment.refresh_from_db()
    assert application.status == "ENROLLED"
    assert application.result_enrollment.status == Enrollment.Status.ACTIVE


@pytest.mark.django_db
def test_create_rejects_new_application_when_active_enrollment_exists(user, student, class_obj):
    from classes.services import AcademicEnrollmentService

    AcademicEnrollmentService(user=user).create_from_application(
        student_id=student.pk,
        class_id=class_obj.pk,
        academic_year=class_obj.academic_year,
        tenant_schema="test_school",
    )
    with pytest.raises(BusinessRuleViolationError):
        _create_application(user, student, class_obj)


@pytest.mark.django_db
def test_reenrollment_batch_rejects_stale_source_version(user, student, class_obj):
    from classes.models import Class
    from classes.services import ClassService
    from enrollments.services import EnrollmentApplicationService, ReenrollmentService

    application_service = EnrollmentApplicationService(user=user)
    original = _create_application(user, student, class_obj)
    original = application_service.submit_application(
        original.pk, expected_version=original.version
    )
    original = application_service.approve_application(
        original.pk, expected_version=original.version
    )
    original = application_service.finalize_application(
        original.pk, expected_version=original.version
    )
    target = ClassService(user=user).create_class(
        {
            "name": "6B Workflow",
            "grade": Class.Grade.ELEMENTARY_6,
            "education_stage": Class.EducationStage.ELEMENTARY_II,
            "academic_year": 2027,
        }
    )

    with pytest.raises(BusinessRuleViolationError):
        ReenrollmentService(user=user).confirm_batch(
            [
                {
                    "source_enrollment_id": original.result_enrollment_id,
                    "target_class_id": target.pk,
                    "expected_version": original.result_enrollment.version + 1,
                }
            ]
        )


@pytest.mark.django_db
def test_reenrollment_batch_rolls_back_all_mappings_when_one_is_stale(user, student, class_obj):
    from classes.models import Class
    from classes.services import ClassService
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService, ReenrollmentService
    from students.models import Student

    second_student = Student.objects.create(
        first_name="Bia",
        last_name="Lote",
        birth_date=dt.date(2014, 7, 1),
        enrollment_number="ALU-WORKFLOW-BATCH-2",
        created_by=user,
        updated_by=user,
    )
    application_service = EnrollmentApplicationService(user=user)
    sources = []
    for current_student in (student, second_student):
        application = _create_application(user, current_student, class_obj)
        application = application_service.submit_application(
            application.pk, expected_version=application.version
        )
        application = application_service.approve_application(
            application.pk, expected_version=application.version
        )
        sources.append(
            application_service.finalize_application(
                application.pk, expected_version=application.version
            ).result_enrollment
        )
    target = ClassService(user=user).create_class(
        {
            "name": "6C Workflow",
            "grade": Class.Grade.ELEMENTARY_6,
            "education_stage": Class.EducationStage.ELEMENTARY_II,
            "academic_year": 2027,
        }
    )

    with pytest.raises(BusinessRuleViolationError):
        ReenrollmentService(user=user).confirm_batch(
            [
                {
                    "source_enrollment_id": sources[0].pk,
                    "target_class_id": target.pk,
                    "expected_version": sources[0].version,
                },
                {
                    "source_enrollment_id": sources[1].pk,
                    "target_class_id": target.pk,
                    "expected_version": sources[1].version + 1,
                },
            ]
        )

    assert not EnrollmentApplication.objects.filter(
        application_type=EnrollmentApplication.ApplicationType.REENROLLMENT
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_reminder_is_published_only_after_commit(user, student, class_obj, monkeypatch):
    from django.db import connection, transaction

    from enrollments.selectors import EnrollmentApplicationSelector
    from enrollments.services import EnrollmentReminderService
    from enrollments.tasks import send_enrollment_document_reminder

    application = _create_application(user, student, class_obj)
    _add_pending_document(user, application)
    monkeypatch.setattr(connection, "schema_name", "tenant_a", raising=False)
    monkeypatch.setattr(
        EnrollmentApplicationSelector,
        "reminder_recipient_ids",
        lambda self, application_id: [user.pk],
    )
    delay = Mock()
    monkeypatch.setattr(send_enrollment_document_reminder, "delay", delay)
    with transaction.atomic():
        EnrollmentReminderService(user=user).send_reminders(
            application.pk, expected_version=application.version
        )
        delay.assert_not_called()
    delay.assert_called_once()
    repeated = EnrollmentReminderService(user=user).send_reminders(
        application.pk, expected_version=application.version
    )
    assert repeated == []
    delay.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize("tenant_schema", ["", "public", "other_school"])
def test_internal_reminder_commands_reject_missing_public_or_mismatched_schema(user, tenant_schema):
    from uuid import uuid4

    from audit.models import AuditLog
    from enrollments.services import EnrollmentReminderService

    service = EnrollmentReminderService(user=None)
    audit_count = AuditLog.objects.count()
    reminder_id = uuid4()

    with pytest.raises(BusinessRuleViolationError):
        service.claim_for_delivery(reminder_id, tenant_schema=tenant_schema)
    with pytest.raises(BusinessRuleViolationError):
        service.reconcile_stale_claims(tenant_schema=tenant_schema)
    with pytest.raises(BusinessRuleViolationError):
        service.record_delivery_result(
            reminder_id,
            tenant_schema=tenant_schema,
            success=True,
        )

    assert AuditLog.objects.count() == audit_count


@pytest.mark.django_db(transaction=True)
def test_reminder_is_not_published_when_audit_rolls_back(user, student, class_obj, monkeypatch):
    from django.db import connection

    from enrollments.selectors import EnrollmentApplicationSelector
    from enrollments.services import EnrollmentReminderService
    from enrollments.tasks import send_enrollment_document_reminder

    application = _create_application(user, student, class_obj)
    _add_pending_document(user, application)
    monkeypatch.setattr(connection, "schema_name", "tenant_a", raising=False)
    monkeypatch.setattr(
        EnrollmentApplicationSelector,
        "reminder_recipient_ids",
        lambda self, application_id: [user.pk],
    )
    service = EnrollmentReminderService(user=user)
    monkeypatch.setattr(
        service,
        "_record_audit",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )
    delay = Mock()
    monkeypatch.setattr(send_enrollment_document_reminder, "delay", delay)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.send_reminders(application.pk, expected_version=application.version)
    delay.assert_not_called()


@pytest.mark.django_db
def test_reminder_recipient_selector_requires_primary_custody_and_consent(user, student, class_obj):
    from core.models import CustomUser, Role
    from enrollments.selectors import EnrollmentApplicationSelector
    from guardians.models import Guardian, StudentGuardian

    recipient = CustomUser.objects.create_user(
        email="guardian-reminder@test.com",
        password="Senha123",
        role=Role.objects.get(name=Role.Name.GUARDIAN),
    )
    guardian = Guardian.objects.create(
        user=recipient,
        first_name="Responsável",
        accepts_email_notifications=True,
        created_by=user,
        updated_by=user,
    )
    link = StudentGuardian.objects.create(
        student=student,
        guardian=guardian,
        is_primary=True,
        has_custody=True,
        created_by=user,
        updated_by=user,
    )
    application = _create_application(user, student, class_obj)
    selector = EnrollmentApplicationSelector()

    assert selector.reminder_recipient_ids(application.pk) == [recipient.pk]

    link.is_active = False
    link.save(update_fields=["is_active"])
    assert selector.reminder_recipient_ids(application.pk) == []


@pytest.mark.django_db(transaction=True)
def test_reminder_claim_revalidates_custody_after_enqueue(user, student, class_obj, monkeypatch):
    from django.db import connection

    from core.models import CustomUser, Role
    from enrollments.models import EnrollmentReminder
    from enrollments.services import EnrollmentReminderService
    from enrollments.tasks import send_enrollment_document_reminder
    from guardians.models import Guardian, StudentGuardian

    recipient = CustomUser.objects.create_user(
        email="guardian-revoked@test.com",
        password="Senha123",
        role=Role.objects.get(name=Role.Name.GUARDIAN),
    )
    guardian = Guardian.objects.create(
        user=recipient,
        first_name="Responsável",
        accepts_email_notifications=True,
        created_by=user,
        updated_by=user,
    )
    link = StudentGuardian.objects.create(
        student=student,
        guardian=guardian,
        is_primary=True,
        has_custody=True,
        created_by=user,
        updated_by=user,
    )
    application = _create_application(user, student, class_obj)
    _add_pending_document(user, application)
    monkeypatch.setattr(connection, "schema_name", "tenant_a", raising=False)
    monkeypatch.setattr(send_enrollment_document_reminder, "delay", Mock())
    reminder = EnrollmentReminderService(user=user).send_reminders(
        application.pk, expected_version=application.version
    )[0]

    link.has_custody = False
    link.save(update_fields=["has_custody"])

    assert (
        EnrollmentReminderService(user=None).claim_for_delivery(
            reminder.pk, tenant_schema="test_school"
        )
        is None
    )
    reminder.refresh_from_db()
    assert reminder.status == EnrollmentReminder.Status.FAILED
    assert reminder.message_log_id is None


@pytest.mark.django_db
def test_abandoned_reminder_claim_reuses_existing_message_log(
    user, student, class_obj, monkeypatch
):
    from datetime import timedelta

    from django.utils import timezone

    from enrollments.models import EnrollmentReminder
    from enrollments.selectors import EnrollmentApplicationSelector
    from enrollments.services import EnrollmentReminderService

    application = _create_application(user, student, class_obj)
    reminder = EnrollmentReminder.objects.create(
        application=application,
        recipient=user,
        created_by=user,
        updated_by=user,
    )
    monkeypatch.setattr(
        EnrollmentApplicationSelector,
        "is_reminder_recipient_eligible",
        lambda self, application_id, recipient_id: True,
    )
    service = EnrollmentReminderService(user=None)
    claimed = service.claim_for_delivery(reminder.pk, tenant_schema="test_school")
    first_log_id = claimed.message_log_id
    EnrollmentReminder.objects.filter(pk=reminder.pk).update(
        updated_at=timezone.now() - timedelta(minutes=16)
    )

    recovered = service.claim_for_delivery(reminder.pk, tenant_schema="test_school")
    assert recovered.pk == reminder.pk
    assert recovered.message_log_id == first_log_id


@pytest.mark.django_db(transaction=True)
def test_stale_reminder_reconciler_republishes_pending_and_closes_terminal_logs(
    user,
    student,
    class_obj,
    monkeypatch,
):
    from datetime import timedelta

    from django.db import connection
    from django.utils import timezone

    from core.models import CustomUser
    from enrollments.models import EnrollmentReminder
    from enrollments.services import EnrollmentReminderService
    from enrollments.tasks import send_enrollment_document_reminder
    from notifications.contracts import MessageLog
    from notifications.delivery_services import MessageDeliveryService

    application = _create_application(user, student, class_obj)
    recipients = [
        user,
        CustomUser.objects.create_user(email="stale-sent@test.com", password="Senha123"),
        CustomUser.objects.create_user(email="stale-failed@test.com", password="Senha123"),
    ]
    abandoned_recipient = CustomUser.objects.create_user(
        email="stale-pending@test.com", password="Senha123"
    )
    message_logs = [
        MessageDeliveryService(user=None).create_pending(
            recipient=recipient,
            channel=MessageLog.Channel.EMAIL,
            recipient_address=recipient.email,
        )
        for recipient in recipients
    ]
    sent_at = timezone.now() - timedelta(minutes=10)
    MessageLog.all_objects.filter(pk=message_logs[1].pk).update(
        status=MessageLog.Status.SENT,
        sent_at=sent_at,
    )
    MessageLog.all_objects.filter(pk=message_logs[2].pk).update(status=MessageLog.Status.FAILED)
    reminders = [
        EnrollmentReminder.objects.create(
            application=application,
            recipient=recipient,
            status=EnrollmentReminder.Status.SENDING,
            message_log_id=message_log.pk,
            created_by=user,
            updated_by=user,
        )
        for recipient, message_log in zip(recipients, message_logs, strict=True)
    ]
    abandoned_reminder = EnrollmentReminder.objects.create(
        application=application,
        recipient=abandoned_recipient,
        status=EnrollmentReminder.Status.PENDING,
        created_by=user,
        updated_by=user,
    )
    EnrollmentReminder.objects.filter(
        pk__in=[item.pk for item in [*reminders, abandoned_reminder]]
    ).update(
        updated_at=timezone.now() - timedelta(minutes=16),
    )
    monkeypatch.setattr(connection, "schema_name", "tenant_a", raising=False)
    delay = Mock()
    monkeypatch.setattr(send_enrollment_document_reminder, "delay", delay)

    recovered = EnrollmentReminderService(user=None).reconcile_stale_claims(
        tenant_schema="test_school"
    )

    for reminder in reminders:
        reminder.refresh_from_db()
    assert recovered == 2
    assert reminders[0].status == EnrollmentReminder.Status.SENDING
    assert reminders[0].message_log_id == message_logs[0].pk
    assert reminders[1].status == EnrollmentReminder.Status.SENT
    assert reminders[1].sent_at == sent_at
    assert reminders[2].status == EnrollmentReminder.Status.FAILED
    abandoned_reminder.refresh_from_db()
    assert abandoned_reminder.status == EnrollmentReminder.Status.PENDING
    delay.assert_has_calls(
        [
            call(
                tenant_schema="test_school",
                reminder_id=str(reminders[0].pk),
                message_log_id=str(message_logs[0].pk),
            ),
            call(
                tenant_schema="test_school",
                reminder_id=str(abandoned_reminder.pk),
            ),
        ],
        any_order=True,
    )
    assert delay.call_count == 2


@pytest.mark.django_db
def test_reminder_retry_does_not_resend_a_message_log_already_sent(
    user,
    student,
    class_obj,
    monkeypatch,
):
    from enrollments.models import EnrollmentReminder
    from enrollments.selectors import EnrollmentApplicationSelector
    from enrollments.services import EnrollmentReminderService
    from notifications.contracts import MessageLog
    from notifications.delivery_services import MessageDeliveryService

    application = _create_application(user, student, class_obj)
    message_log = MessageDeliveryService(user=None).create_pending(
        recipient=user,
        channel=MessageLog.Channel.EMAIL,
        recipient_address=user.email,
    )
    MessageLog.all_objects.filter(pk=message_log.pk).update(status=MessageLog.Status.SENT)
    reminder = EnrollmentReminder.objects.create(
        application=application,
        recipient=user,
        status=EnrollmentReminder.Status.SENDING,
        message_log_id=message_log.pk,
        created_by=user,
        updated_by=user,
    )
    monkeypatch.setattr(
        EnrollmentApplicationSelector,
        "is_reminder_recipient_eligible",
        lambda self, application_id, recipient_id: True,
    )

    claimed = EnrollmentReminderService(user=None).claim_for_delivery(
        reminder.pk,
        tenant_schema="test_school",
        message_log_id=message_log.pk,
    )

    reminder.refresh_from_db()
    assert claimed is None
    assert reminder.status == EnrollmentReminder.Status.SENT


@pytest.mark.django_db(transaction=True)
def test_failed_reminder_requeue_uses_a_new_message_log(
    user, student, class_obj, monkeypatch, caplog
):
    from django.db import connection

    from enrollments.models import EnrollmentReminder
    from enrollments.selectors import EnrollmentApplicationSelector
    from enrollments.services import EnrollmentReminderService
    from enrollments.tasks import send_enrollment_document_reminder

    application = _create_application(user, student, class_obj)
    _add_pending_document(user, application)
    monkeypatch.setattr(connection, "schema_name", "tenant_a", raising=False)
    monkeypatch.setattr(
        EnrollmentApplicationSelector,
        "reminder_recipient_ids",
        lambda self, application_id: [user.pk],
    )
    monkeypatch.setattr(send_enrollment_document_reminder, "delay", Mock())
    service = EnrollmentReminderService(user=user)
    caplog.set_level(logging.INFO, logger="base.services")

    reminder = service.send_reminders(application.pk, expected_version=application.version)[0]
    claimed = EnrollmentReminderService(user=None).claim_for_delivery(
        reminder.pk, tenant_schema="test_school"
    )
    claim_record = next(
        record for record in caplog.records if record.getMessage() == "enrollment_reminder_claimed"
    )
    assert claim_record.reminder_id == str(reminder.pk)
    assert claim_record.message_log_id == str(claimed.message_log_id)
    assert claim_record.from_status == EnrollmentReminder.Status.PENDING
    assert claim_record.to_status == EnrollmentReminder.Status.SENDING
    assert not hasattr(claim_record, "email")
    first_log_id = claimed.message_log_id
    EnrollmentReminderService(user=None).record_delivery_result(
        reminder.pk,
        tenant_schema="test_school",
        success=False,
        message_log_id=first_log_id,
    )

    requeued = service.send_reminders(application.pk, expected_version=application.version)
    reminder.refresh_from_db()
    assert requeued == [reminder]
    assert reminder.status == EnrollmentReminder.Status.PENDING
    assert reminder.message_log_id is None

    claimed = EnrollmentReminderService(user=None).claim_for_delivery(
        reminder.pk, tenant_schema="test_school"
    )
    assert claimed.message_log_id != first_log_id
    assert (
        EnrollmentReminderService(user=None).claim_for_delivery(
            reminder.pk, tenant_schema="test_school"
        )
        is None
    )
    assert (
        EnrollmentReminderService(user=None)
        .claim_for_delivery(
            reminder.pk,
            tenant_schema="test_school",
            message_log_id=claimed.message_log_id,
        )
        .pk
        == reminder.pk
    )


@pytest.mark.django_db
def test_priority_outside_storage_range_is_rejected(user, student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService

    with pytest.raises(ValidationError):
        EnrollmentApplicationService(user=user).create_application(
            {
                "student_id": student.pk,
                "target_class_id": class_obj.pk,
                "application_type": EnrollmentApplication.ApplicationType.NEW,
                "priority": 32768,
            }
        )


@pytest.mark.django_db
def test_application_detail_projection_materializes_capacity_documents_and_transitions(
    user, student, class_obj
):
    from enrollments.selectors import ApplicationDetail, EnrollmentApplicationSelector

    application = _create_application(user, student, class_obj)
    _add_pending_document(user, application)

    detail = EnrollmentApplicationSelector().get_application_detail(application.pk)

    assert isinstance(detail, ApplicationDetail)
    assert detail.application.pk == application.pk
    assert isinstance(detail.documents, tuple)
    assert isinstance(detail.transitions, tuple)
    assert detail.has_pending_required_documents is True
    assert detail.pending_required_document_count == 1
    assert detail.can_finalize is False
    assert detail.waitlist_position is None
    assert detail.waitlist_total is None
    assert detail.capacity.maximum == class_obj.max_students
    assert detail.capacity.committed == 0


@pytest.mark.django_db
def test_services_translate_invalid_uuids_and_storage_lengths(user, student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService, StudentDocumentService

    application_service = EnrollmentApplicationService(user=user)
    with pytest.raises(ValidationError):
        application_service.create_application(
            {
                "student_id": "not-a-uuid",
                "target_class_id": class_obj.pk,
                "application_type": EnrollmentApplication.ApplicationType.NEW,
            }
        )
    with pytest.raises(ValidationError):
        application_service.create_application(
            {
                "student_id": student.pk,
                "target_class_id": "not-a-uuid",
                "application_type": EnrollmentApplication.ApplicationType.NEW,
            }
        )
    with pytest.raises(ValidationError) as school_error:
        application_service.create_application(
            {
                "student_id": student.pk,
                "target_class_id": class_obj.pk,
                "application_type": EnrollmentApplication.ApplicationType.INBOUND_TRANSFER,
                "origin_school": "x" * 201,
            }
        )
    assert "origin_school" in school_error.value.errors

    document_service = StudentDocumentService(user=user)
    with pytest.raises(ValidationError) as label_error:
        document_service.create_requirement(
            {
                "application_type": EnrollmentApplication.ApplicationType.NEW,
                "code": "long-label",
                "label": "x" * 121,
            }
        )
    assert "label" in label_error.value.errors
    with pytest.raises(ValidationError):
        document_service.update_requirement("not-a-uuid", {}, expected_version=0)


@pytest.mark.django_db
def test_application_and_batch_services_reject_oversized_notes_directly(user, student, class_obj):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService, ReenrollmentService

    service = EnrollmentApplicationService(user=user)
    with pytest.raises(ValidationError) as create_error:
        service.create_application(
            {
                "student_id": student.pk,
                "target_class_id": class_obj.pk,
                "application_type": EnrollmentApplication.ApplicationType.NEW,
                "notes": "x" * 1001,
            }
        )
    assert "notes" in create_error.value.errors

    application = _create_application(user, student, class_obj)
    with pytest.raises(ValidationError) as correction_error:
        service.correct_application(
            application.pk,
            {"target_class_id": class_obj.pk, "notes": "x" * 1001},
            expected_version=application.version,
        )
    assert "notes" in correction_error.value.errors

    with pytest.raises(ValidationError) as batch_error:
        ReenrollmentService(user=user).confirm_batch(
            [
                {
                    "source_enrollment_id": application.pk,
                    "target_class_id": class_obj.pk,
                    "expected_version": 0,
                    "exception_reason": "x" * 1001,
                }
            ]
        )
    assert "exception_reason" in batch_error.value.errors


@pytest.mark.django_db
def test_reenrollment_batch_rejects_malformed_identifiers(user):
    from enrollments.services import ReenrollmentService

    with pytest.raises(ValidationError):
        ReenrollmentService(user=user).confirm_batch(
            [
                {
                    "source_enrollment_id": "not-a-uuid",
                    "target_class_id": "",
                    "expected_version": 0,
                }
            ]
        )


@pytest.mark.django_db
def test_authenticated_user_without_create_or_edit_cannot_execute_enrollment_commands(
    user, student, class_obj
):
    from django.utils import timezone

    from core.models import Role, RoleModuleAccess
    from enrollments.models import EnrollmentApplication
    from enrollments.services import (
        EnrollmentApplicationService,
        ReenrollmentService,
        StudentDocumentService,
    )

    application = _create_application(user, student, class_obj)
    document = _add_pending_document(user, application)
    coordinator = Role.objects.get(name=Role.Name.COORDINATOR)
    RoleModuleAccess.objects.update_or_create(
        role=coordinator,
        module_key="enrollments",
        defaults={
            "can_view": True,
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
    if hasattr(user, "_role_access_cache"):
        del user._role_access_cache

    applications = EnrollmentApplicationService(user=user)
    denied_commands = (
        lambda: applications.create_application(
            {
                "student_id": student.pk,
                "target_class_id": class_obj.pk,
                "application_type": EnrollmentApplication.ApplicationType.NEW,
            }
        ),
        lambda: applications.correct_application(application.pk, {}, expected_version=0),
        lambda: applications.submit_application(application.pk, expected_version=0),
        lambda: applications.approve_application(application.pk, expected_version=0),
        lambda: applications.request_correction(application.pk, "Motivo", expected_version=0),
        lambda: applications.reject_application(application.pk, "Motivo", expected_version=0),
        lambda: applications.finalize_application(application.pk, expected_version=0),
        lambda: applications.cancel_application(application.pk, "Motivo", expected_version=0),
    )
    for command in denied_commands:
        with pytest.raises(PermissionDeniedError):
            command()

    documents = StudentDocumentService(user=user)
    denied_document_commands = (
        lambda: documents.record_delivery(
            document.pk, delivery_method="PHYSICAL", expected_version=0
        ),
        lambda: documents.verify_document(document.pk, expected_version=0),
        lambda: documents.reject_document(document.pk, "Motivo", expected_version=0),
        lambda: documents.waive_document(document.pk, "Motivo", expected_version=0),
    )
    for command in denied_document_commands:
        with pytest.raises(PermissionDeniedError):
            command()
    with pytest.raises(PermissionDeniedError):
        ReenrollmentService(user=user).confirm_batch([])


@pytest.mark.django_db
def test_document_waiver_is_admin_only_and_cannot_be_repeated(user, student, class_obj):
    from core.models import CustomUser, Role, RoleModuleAccess
    from enrollments.models import EnrollmentApplication, StudentDocument
    from enrollments.services import StudentDocumentService

    service = StudentDocumentService(user=user)
    service.create_requirement(
        {
            "application_type": EnrollmentApplication.ApplicationType.NEW,
            "code": "waiver",
            "label": "Documento dispensável",
        }
    )
    application = _create_application(user, student, class_obj)
    document = application.documents.get()
    document = service.waive_document(
        document.pk,
        "Exceção autorizada",
        expected_version=document.version,
    )
    assert document.status == StudentDocument.Status.WAIVED
    assert document.decision_reason == "Exceção autorizada"

    with pytest.raises(BusinessRuleViolationError):
        service.waive_document(
            document.pk,
            "Outra exceção",
            expected_version=document.version,
        )

    secretary = CustomUser.objects.create_user(
        email="secretary-waiver@test.com",
        password="Senha123",
        role=Role.objects.get(name=Role.Name.SECRETARY),
    )
    RoleModuleAccess.objects.filter(
        role=secretary.role,
        module_key="document_requirements",
    ).update(
        can_view=True,
        can_create=True,
        can_edit=True,
        can_deactivate=True,
    )
    with pytest.raises(PermissionDeniedError):
        StudentDocumentService(user=secretary).waive_document(
            document.pk,
            "Tentativa indevida",
            expected_version=document.version,
        )


@pytest.mark.django_db
def test_document_upload_is_deleted_when_audit_rolls_back(user, student, class_obj, monkeypatch):
    from base.tests.images import png_upload
    from enrollments.models import StudentDocument
    from enrollments.services import StudentDocumentService

    application = _create_application(user, student, class_obj)
    document = StudentDocument.objects.create(
        application=application,
        requirement_code="rollback-file",
        requirement_label="Arquivo com rollback",
        created_by=user,
        updated_by=user,
    )
    storage = document.file.storage
    deleted_names = []
    real_delete = storage.delete

    def tracked_delete(name):
        deleted_names.append(name)
        return real_delete(name)

    service = StudentDocumentService(user=user)
    monkeypatch.setattr(storage, "delete", tracked_delete)
    monkeypatch.setattr(
        service,
        "_record_audit",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.record_delivery(
            document.pk,
            delivery_method=StudentDocument.DeliveryMethod.DIGITAL,
            file=png_upload("rollback.png"),
            expected_version=document.version,
        )

    assert len(deleted_names) == 1
    assert not storage.exists(deleted_names[0])
