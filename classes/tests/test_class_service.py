"""Testes do ClassService."""

import datetime as dt

import pytest

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from classes.models import Class, Enrollment
from classes.services import ClassService
from core.models import CustomUser
from students.models import Student
from teachers.models import Teacher

_BASE_CLASS_DATA = {
    "name": "1A",
    "grade": Class.Grade.ELEMENTARY_1,
    "education_stage": Class.EducationStage.ELEMENTARY_I,
    "academic_year": 2025,
    "shift": Class.Shift.MORNING,
    "max_students": 30,
}


def _make_user(email="school@test.com"):
    return CustomUser.objects.create_user(
        email=email, password="Senha123", first_name="Admin", last_name="Escola"
    )


def _make_student(user, enrollment_number="S-001"):
    return Student.objects.create(
        first_name="João",
        last_name="Silva",
        birth_date=dt.date(2010, 5, 15),
        enrollment_number=enrollment_number,
        created_by=user,
        updated_by=user,
    )


def _make_teacher(user, registration="T-001"):
    target = _make_user(f"teacher{registration}@test.com")
    return Teacher.objects.create(
        user=target, registration_number=registration, created_by=user, updated_by=user
    )


@pytest.mark.django_db
class TestCreateClass:
    def test_success(self, user):
        cls = ClassService(user=user).create_class(_BASE_CLASS_DATA)
        assert cls.pk is not None
        assert cls.name == "1A"
        assert cls.grade == Class.Grade.ELEMENTARY_1

    def test_duplicate_name_in_same_year(self, user):
        ClassService(user=user).create_class(_BASE_CLASS_DATA)
        with pytest.raises(ValidationError):
            ClassService(user=user).create_class(_BASE_CLASS_DATA)

    def test_name_different_year_allowed(self, user):
        ClassService(user=user).create_class(_BASE_CLASS_DATA)
        cls = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "academic_year": 2026})
        assert cls.pk is not None

    def test_missing_required_fields(self, user):
        with pytest.raises(ValidationError):
            ClassService(user=user).create_class({"name": "1B"})

    def test_with_class_teacher(self, user):
        teacher = _make_teacher(user)
        cls = ClassService(user=user).create_class(
            {**_BASE_CLASS_DATA, "class_teacher_id": teacher.pk}
        )
        assert cls.class_teacher == teacher

    def test_with_invalid_teacher(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            ClassService(user=user).create_class(
                {**_BASE_CLASS_DATA, "class_teacher_id": uuid.uuid4()}
            )

    def test_rejects_grade_from_another_education_stage(self, user):
        with pytest.raises(ValidationError) as exc_info:
            ClassService(user=user).create_class(
                {
                    **_BASE_CLASS_DATA,
                    "grade": Class.Grade.HIGH_SCHOOL_1,
                }
            )

        assert "grade" in exc_info.value.errors

    def test_rejects_unknown_legacy_grade(self, user):
        with pytest.raises(ValidationError) as exc_info:
            ClassService(user=user).create_class(
                {**_BASE_CLASS_DATA, "grade": "Série Experimental"}
            )

        assert "grade" in exc_info.value.errors


@pytest.mark.django_db
class TestUpdateClass:
    def test_success(self, user):
        cls = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "UPD-A"})
        updated = ClassService(user=user).update_class(cls.pk, {"name": "1B"})
        assert updated.name == "1B"

    def test_change_teacher(self, user):
        teacher1 = _make_teacher(user, "T-10")
        teacher2 = _make_teacher(user, "T-20")
        cls = ClassService(user=user).create_class(
            {**_BASE_CLASS_DATA, "class_teacher_id": teacher1.pk}
        )
        updated = ClassService(user=user).update_class(cls.pk, {"class_teacher_id": teacher2.pk})
        assert updated.class_teacher == teacher2

    def test_remove_teacher(self, user):
        teacher = _make_teacher(user, "T-30")
        cls = ClassService(user=user).create_class(
            {**_BASE_CLASS_DATA, "class_teacher_id": teacher.pk}
        )
        updated = ClassService(user=user).update_class(cls.pk, {"class_teacher_id": None})
        assert updated.class_teacher is None

    def test_rejects_incompatible_stage_change(self, user):
        cls = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "UPD-STAGE"})

        with pytest.raises(ValidationError) as exc_info:
            ClassService(user=user).update_class(
                cls.pk, {"education_stage": Class.EducationStage.HIGH_SCHOOL}
            )

        assert "grade" in exc_info.value.errors


@pytest.mark.django_db
class TestDeactivateClass:
    def test_success(self, user):
        cls = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "DEL-A"})
        ClassService(user=user).deactivate_class(cls.pk)
        cls.refresh_from_db()
        assert cls.deleted_at is not None

    def test_already_deactivated(self, user):
        cls = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "DEL-B"})
        ClassService(user=user).deactivate_class(cls.pk)
        with pytest.raises(BusinessRuleViolationError):
            ClassService(user=user).deactivate_class(cls.pk)


@pytest.mark.django_db
class TestEnrollStudent:
    def test_success(self, user):
        cls = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "ENR-A"})
        student = _make_student(user, "ENR-001")
        enrollment = ClassService(user=user).enroll_student(cls.pk, student.pk)
        assert enrollment.pk is not None
        assert enrollment.status == Enrollment.Status.ACTIVE

    def test_duplicate_enrollment(self, user):
        cls = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "ENR-B"})
        student = _make_student(user, "ENR-002")
        ClassService(user=user).enroll_student(cls.pk, student.pk)
        with pytest.raises(BusinessRuleViolationError):
            ClassService(user=user).enroll_student(cls.pk, student.pk)

    def test_no_open_seats(self, user):
        cls = ClassService(user=user).create_class(
            {**_BASE_CLASS_DATA, "name": "FULL", "max_students": 1}
        )
        s1 = _make_student(user, "FULL-001")
        s2 = _make_student(user, "FULL-002")
        ClassService(user=user).enroll_student(cls.pk, s1.pk)
        with pytest.raises(BusinessRuleViolationError):
            ClassService(user=user).enroll_student(cls.pk, s2.pk)

    def test_student_not_found(self, user):
        import uuid

        cls = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "ENR-C"})
        with pytest.raises(ObjectNotFoundError):
            ClassService(user=user).enroll_student(cls.pk, uuid.uuid4())


@pytest.mark.django_db
class TestTransferStudent:
    def test_success(self, user):
        cls_a = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "TRF-A"})
        cls_b = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "TRF-B"})
        student = _make_student(user, "TRF-001")
        ClassService(user=user).enroll_student(cls_a.pk, student.pk)
        new_enrollment = ClassService(user=user).transfer_student(student.pk, cls_a.pk, cls_b.pk)
        assert new_enrollment.class_obj == cls_b
        assert new_enrollment.status == Enrollment.Status.ACTIVE
        old = Enrollment.all_objects.get(student=student, class_obj=cls_a)
        assert old.status == Enrollment.Status.TRANSFERRED

    def test_not_enrolled_in_from_class(self, user):
        cls_a = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "TRF-C"})
        cls_b = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "TRF-D"})
        student = _make_student(user, "TRF-002")
        with pytest.raises(BusinessRuleViolationError):
            ClassService(user=user).transfer_student(student.pk, cls_a.pk, cls_b.pk)

    def test_already_enrolled_in_destination(self, user):
        cls_a = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "TRF-E"})
        cls_b = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "TRF-F"})
        student = _make_student(user, "TRF-003")
        ClassService(user=user).enroll_student(cls_a.pk, student.pk)
        ClassService(user=user).enroll_student(cls_b.pk, student.pk)
        with pytest.raises(BusinessRuleViolationError):
            ClassService(user=user).transfer_student(student.pk, cls_a.pk, cls_b.pk)

    def test_destination_full(self, user):
        cls_a = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "TRF-G"})
        cls_b = ClassService(user=user).create_class(
            {**_BASE_CLASS_DATA, "name": "TRF-H", "max_students": 1}
        )
        student = _make_student(user, "TRF-004")
        other = _make_student(user, "TRF-005")
        ClassService(user=user).enroll_student(cls_a.pk, student.pk)
        ClassService(user=user).enroll_student(cls_b.pk, other.pk)
        with pytest.raises(BusinessRuleViolationError):
            ClassService(user=user).transfer_student(student.pk, cls_a.pk, cls_b.pk)


@pytest.mark.django_db
class TestUnenrollStudent:
    def test_success(self, user):
        cls = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "UNR-A"})
        student = _make_student(user, "UNR-001")
        enrollment = ClassService(user=user).enroll_student(cls.pk, student.pk)
        updated = ClassService(user=user).unenroll_student(enrollment.pk, "Motivo pessoal")
        assert updated.status == Enrollment.Status.CANCELLED
        assert updated.cancel_reason == "Motivo pessoal"

    def test_deactivate_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            ClassService(user=user).deactivate_class(uuid.uuid4())

    def test_update_with_invalid_teacher(self, user):
        import uuid

        cls = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "INV-TCH"})
        with pytest.raises(ObjectNotFoundError):
            ClassService(user=user).update_class(cls.pk, {"class_teacher_id": uuid.uuid4()})

    def test_transfer_student_not_found(self, user):
        import uuid

        cls_a = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "TRF-XX"})
        cls_b = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "TRF-YY"})
        with pytest.raises(ObjectNotFoundError):
            ClassService(user=user).transfer_student(uuid.uuid4(), cls_a.pk, cls_b.pk)

    def test_unenroll_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            ClassService(user=user).unenroll_student(uuid.uuid4())

    def test_already_cancelled(self, user):
        cls = ClassService(user=user).create_class({**_BASE_CLASS_DATA, "name": "UNR-B"})
        student = _make_student(user, "UNR-002")
        enrollment = ClassService(user=user).enroll_student(cls.pk, student.pk)
        ClassService(user=user).unenroll_student(enrollment.pk)
        with pytest.raises(BusinessRuleViolationError):
            ClassService(user=user).unenroll_student(enrollment.pk)
