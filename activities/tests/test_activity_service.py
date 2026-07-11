"""Testes do ActivityService."""

import datetime as dt
from decimal import Decimal

import pytest

from activities.services import ActivityService
from base.exceptions import ObjectNotFoundError, ValidationError
from classes.models import Class, Enrollment
from core.models import CustomUser
from students.models import Student
from teachers.models import Subject, Teacher


def _make_user(email="act@test.com"):
    return CustomUser.objects.create_user(
        email=email, password="Senha123", first_name="Prof", last_name="Activity"
    )


def _make_class(user):
    return Class.objects.create(
        name="1A",
        grade="1º Ano",
        academic_year=2025,
        shift=Class.Shift.MORNING,
        created_by=user,
        updated_by=user,
    )


def _make_subject(user):
    return Subject.objects.create(name="Matemática", code="MAT", created_by=user, updated_by=user)


def _make_teacher(user, registration="ACT-001"):
    target = _make_user(f"act-teacher{registration}@test.com")
    return Teacher.objects.create(
        user=target, registration_number=registration, created_by=user, updated_by=user
    )


def _make_student(user, enrollment_number="ACT-S001"):
    return Student.objects.create(
        first_name="Maria",
        last_name="Souza",
        birth_date=dt.date(2010, 5, 15),
        enrollment_number=enrollment_number,
        created_by=user,
        updated_by=user,
    )


def _enroll(user, student, class_obj, status=Enrollment.Status.ACTIVE):
    return Enrollment.objects.create(
        student=student,
        class_obj=class_obj,
        enrollment_date=dt.date.today(),
        status=status,
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
class TestCreateActivity:
    def test_success(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user)
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova 1",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        assert activity.pk is not None
        assert activity.title == "Prova 1"
        assert activity.max_score == Decimal("10")
        assert activity.submissions.filter(student=student, score__isnull=True).exists()

    def test_missing_required_fields(self, user):
        with pytest.raises(ValidationError):
            ActivityService(user=user).create_activity({})

    def test_invalid_max_score(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        with pytest.raises(ValidationError):
            ActivityService(user=user).create_activity(
                {
                    "class_obj_id": cls.pk,
                    "subject_id": subject.pk,
                    "teacher_id": teacher.pk,
                    "title": "Prova X",
                    "due_date": dt.date(2025, 4, 10),
                    "max_score": 0,
                }
            )

    def test_class_not_found(self, user):
        import uuid

        subject = _make_subject(user)
        teacher = _make_teacher(user)
        with pytest.raises(ObjectNotFoundError):
            ActivityService(user=user).create_activity(
                {
                    "class_obj_id": uuid.uuid4(),
                    "subject_id": subject.pk,
                    "teacher_id": teacher.pk,
                    "title": "Prova X",
                    "due_date": dt.date(2025, 4, 10),
                    "max_score": 10,
                }
            )


@pytest.mark.django_db
class TestUpdateActivity:
    def test_success(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova A",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        updated = ActivityService(user=user).update_activity(
            activity.pk, {"title": "Prova B", "max_score": 8}
        )
        assert updated.title == "Prova B"
        assert updated.max_score == Decimal("8")


@pytest.mark.django_db
class TestRecordScore:
    def test_success_first_record(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user)
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova C",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        sub = ActivityService(user=user).record_score(activity.pk, student.pk, 8.5, "Bom trabalho!")
        assert sub.pk is not None
        assert sub.score == Decimal("8.5")
        assert sub.feedback == "Bom trabalho!"
        assert sub.submitted_at is not None

    def test_update_existing_score(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "UPD-S001")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova D",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        ActivityService(user=user).record_score(activity.pk, student.pk, 7.0)
        sub = ActivityService(user=user).record_score(activity.pk, student.pk, 9.0)
        assert sub.score == Decimal("9.0")

    def test_score_out_of_range(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "S-OUT")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova E",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        with pytest.raises(ValidationError):
            ActivityService(user=user).record_score(activity.pk, student.pk, 15)

    def test_negative_score(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "S-NEG")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova F",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        with pytest.raises(ValidationError):
            ActivityService(user=user).record_score(activity.pk, student.pk, -1)

    def test_student_not_found(self, user):
        import uuid

        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova G",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        with pytest.raises(ObjectNotFoundError):
            ActivityService(user=user).record_score(activity.pk, uuid.uuid4(), 5)


@pytest.mark.django_db
class TestBatchRecordScores:
    def test_success(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "BATCH-001")
        s2 = _make_student(user, "BATCH-002")
        _enroll(user, s1, cls)
        _enroll(user, s2, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova Batch",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        result = ActivityService(user=user).batch_record_scores(
            activity.pk,
            [
                {"student_id": s1.pk, "score": 8, "feedback": "OK"},
                {"student_id": s2.pk, "score": 6},
            ],
        )
        assert result["created"] == 2
        assert len(result["errors"]) == 0

    def test_partial_errors(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "BATCH-E1")
        _enroll(user, s1, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova BatchErr",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        result = ActivityService(user=user).batch_record_scores(
            activity.pk,
            [
                {"student_id": s1.pk, "score": 7},
                {"student_id": "NOPE-XXX", "score": 5},
            ],
        )
        assert result["created"] == 1
        assert len(result["errors"]) == 1
