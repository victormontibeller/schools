"""Testes do cadastro de turmas e da porta acadêmica interna."""

import datetime as dt
import uuid

import pytest

from agenda.models import Schedule, TimeSlot
from audit.models import AuditLog
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from classes.models import Class, Enrollment
from classes.services import AcademicEnrollmentService, ClassService
from students.models import Student
from teachers.models import Subject, Teacher

_BASE_CLASS_DATA = {
    "name": "1A",
    "grade": Class.Grade.ELEMENTARY_1,
    "education_stage": Class.EducationStage.ELEMENTARY_I,
    "academic_year": 2026,
    "shift": Class.Shift.MORNING,
    "max_students": 30,
}


def _student(user, number="S-001"):
    return Student.objects.create(
        first_name="João",
        last_name="Silva",
        birth_date=dt.date(2018, 5, 15),
        enrollment_number=number,
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
def test_create_class_succeeds(user):
    class_obj = ClassService(user=user).create_class(_BASE_CLASS_DATA)
    assert class_obj.grade == Class.Grade.ELEMENTARY_1


@pytest.mark.django_db
def test_create_class_rejects_duplicate(user):
    ClassService(user=user).create_class(_BASE_CLASS_DATA)
    with pytest.raises(ValidationError):
        ClassService(user=user).create_class(_BASE_CLASS_DATA)


@pytest.mark.django_db
def test_create_class_rejects_grade_outside_stage(user):
    with pytest.raises(ValidationError):
        ClassService(user=user).create_class(
            {**_BASE_CLASS_DATA, "grade": Class.Grade.HIGH_SCHOOL_1}
        )


@pytest.mark.django_db
def test_create_class_allows_same_name_in_another_year(user):
    ClassService(user=user).create_class(_BASE_CLASS_DATA)
    created = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "academic_year": 2027})
    assert created.academic_year == 2027


@pytest.mark.django_db
def test_create_class_rejects_missing_required_fields(user):
    with pytest.raises(ValidationError):
        ClassService(user=user).create_class({"name": "Incompleta"})


@pytest.mark.django_db
def test_create_class_rejects_unknown_grade(user):
    with pytest.raises(ValidationError):
        ClassService(user=user).create_class({**_BASE_CLASS_DATA, "grade": "LEGACY"})


@pytest.mark.django_db
def test_create_class_rejects_unknown_shift(user):
    with pytest.raises(ValidationError) as exc_info:
        ClassService(user=user).create_class({**_BASE_CLASS_DATA, "shift": "UNKNOWN"})

    assert exc_info.value.errors == {"shift": ["Selecione um turno válido."]}


@pytest.mark.django_db
def test_update_class_changes_name(user):
    class_obj = ClassService(user=user).create_class(_BASE_CLASS_DATA)
    updated = ClassService(user=user).update_class(class_obj.pk, {"name": "1B"})
    assert updated.name == "1B"


@pytest.mark.django_db
def test_update_class_rejects_unknown_shift(user):
    class_obj = ClassService(user=user).create_class(_BASE_CLASS_DATA)

    with pytest.raises(ValidationError) as exc_info:
        ClassService(user=user).update_class(
            class_obj.pk,
            {"shift": "UNKNOWN", "version": class_obj.version},
        )

    assert exc_info.value.errors == {"shift": ["Selecione um turno válido."]}
    class_obj.refresh_from_db()
    assert class_obj.shift == Class.Shift.MORNING


@pytest.mark.django_db
def test_update_class_allows_shift_change_without_schedule_history(user):
    class_obj = ClassService(user=user).create_class(_BASE_CLASS_DATA)

    updated = ClassService(user=user).update_class(
        class_obj.pk,
        {"shift": Class.Shift.AFTERNOON, "version": class_obj.version},
    )

    assert updated.shift == Class.Shift.AFTERNOON

    audit = AuditLog.objects.get(
        operation=AuditLog.Operation.UPDATE,
        model_name="Class",
        object_id=str(class_obj.pk),
    )
    assert audit.old_values["shift"] == Class.Shift.MORNING
    assert audit.new_values["shift"] == Class.Shift.AFTERNOON


@pytest.mark.django_db
def test_update_class_rejects_shift_change_with_inactive_schedule_history(user):
    from core.models import CustomUser

    class_obj = ClassService(user=user).create_class(_BASE_CLASS_DATA)
    teacher_user = CustomUser.objects.create_user(
        email="history-teacher@class.test", password="Senha123"
    )
    teacher = Teacher.objects.create(
        user=teacher_user,
        registration_number="CLASS-HISTORY-001",
        created_by=user,
        updated_by=user,
    )
    subject = Subject.objects.create(
        name="História da turma", code="HST", created_by=user, updated_by=user
    )
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    schedule = Schedule.objects.create(
        class_obj=class_obj,
        teacher=teacher,
        subject=subject,
        time_slot=slot,
        day_of_week=Schedule.Day.MON,
        valid_from=dt.date(2025, 1, 6),
        valid_until=dt.date(2025, 12, 28),
        created_by=user,
        updated_by=user,
    )
    schedule.soft_delete(user=user)

    with pytest.raises(BusinessRuleViolationError):
        ClassService(user=user).update_class(
            class_obj.pk,
            {"shift": Class.Shift.AFTERNOON, "version": class_obj.version},
        )

    class_obj.refresh_from_db()
    assert class_obj.shift == Class.Shift.MORNING


@pytest.mark.django_db
def test_update_class_rejects_incompatible_stage(user):
    class_obj = ClassService(user=user).create_class(_BASE_CLASS_DATA)
    with pytest.raises(ValidationError):
        ClassService(user=user).update_class(
            class_obj.pk, {"education_stage": Class.EducationStage.HIGH_SCHOOL}
        )


@pytest.mark.django_db
def test_deactivate_class_soft_deletes_and_rejects_repeat(user):
    class_obj = ClassService(user=user).create_class(_BASE_CLASS_DATA)
    ClassService(user=user).deactivate_class(class_obj.pk)
    class_obj.refresh_from_db()
    assert class_obj.deleted_at is not None
    with pytest.raises(BusinessRuleViolationError):
        ClassService(user=user).deactivate_class(class_obj.pk)


@pytest.mark.django_db
def test_internal_academic_service_creates_year_scoped_enrollment(user):
    class_obj = ClassService(user=user).create_class(_BASE_CLASS_DATA)
    student = _student(user)
    enrollment = AcademicEnrollmentService(user=user).create_from_application(
        student_id=student.pk,
        class_id=class_obj.pk,
        academic_year=class_obj.academic_year,
        tenant_schema="test_school",
    )
    assert enrollment.academic_year == 2026
    assert enrollment.status == Enrollment.Status.ACTIVE


@pytest.mark.django_db
def test_internal_academic_service_rejects_second_active_year(user):
    first = ClassService(user=user).create_class(_BASE_CLASS_DATA)
    second = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "1B"})
    student = _student(user)
    service = AcademicEnrollmentService(user=user)
    service.create_from_application(
        student_id=student.pk,
        class_id=first.pk,
        academic_year=2026,
        tenant_schema="test_school",
    )
    with pytest.raises(BusinessRuleViolationError):
        service.create_from_application(
            student_id=student.pk,
            class_id=second.pk,
            academic_year=2026,
            tenant_schema="test_school",
        )


@pytest.mark.django_db
def test_internal_academic_close_validates_reason_existence_and_active_status(user):
    class_obj = ClassService(user=user).create_class(_BASE_CLASS_DATA)
    student = _student(user)
    service = AcademicEnrollmentService(user=user)
    enrollment = service.create_from_application(
        student_id=student.pk,
        class_id=class_obj.pk,
        academic_year=class_obj.academic_year,
        tenant_schema="test_school",
    )

    with pytest.raises(ValidationError):
        service.close_from_application(
            enrollment_id=enrollment.pk, reason="", tenant_schema="test_school"
        )
    with pytest.raises(ValidationError):
        service.close_from_application(
            enrollment_id=enrollment.pk, reason="x" * 201, tenant_schema="test_school"
        )
    with pytest.raises(ObjectNotFoundError):
        service.close_from_application(
            enrollment_id=uuid.uuid4(),
            reason="Motivo válido",
            tenant_schema="test_school",
        )

    service.close_from_application(
        enrollment_id=enrollment.pk,
        reason="Motivo válido",
        tenant_schema="test_school",
    )
    with pytest.raises(BusinessRuleViolationError):
        service.close_from_application(
            enrollment_id=enrollment.pk,
            reason="Repetido",
            tenant_schema="test_school",
        )


@pytest.mark.django_db
@pytest.mark.parametrize("tenant_schema", ["", "public", "other_school"])
def test_internal_academic_service_rejects_missing_public_or_mismatched_schema(user, tenant_schema):
    class_obj = ClassService(user=user).create_class(_BASE_CLASS_DATA)
    student = _student(user)

    with pytest.raises(BusinessRuleViolationError):
        AcademicEnrollmentService(user=user).create_from_application(
            student_id=student.pk,
            class_id=class_obj.pk,
            academic_year=class_obj.academic_year,
            tenant_schema=tenant_schema,
        )

    assert not Enrollment.objects.filter(student=student).exists()
