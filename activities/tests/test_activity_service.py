"""Testes do ActivityService."""

import datetime as dt
from decimal import Decimal

import pytest

from activities.models import Activity, ActivityGroup, ActivityGroupMember, ActivitySubmission
from activities.services import ActivityService
from agenda.models import Schedule, TimeSlot
from audit.models import AuditLog
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from classes.models import Class, Enrollment
from core.models import CustomUser, Role
from students.models import Student
from teachers.models import Subject, Teacher


def _make_user(email="act@test.com"):
    return CustomUser.objects.create_user(
        email=email, password="Senha123", first_name="Prof", last_name="Activity"
    )


def _make_class(user, name="1A"):
    return Class.objects.create(
        name=name,
        grade=Class.Grade.ELEMENTARY_1,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=2025,
        shift=Class.Shift.MORNING,
        created_by=user,
        updated_by=user,
    )


def _make_subject(user):
    return Subject.objects.create(name="Matemática", code="MAT", created_by=user, updated_by=user)


def _make_schedule(
    user,
    class_obj,
    subject,
    teacher,
    *,
    valid_from=dt.date(2020, 1, 1),
    valid_until=None,
):
    slot, _ = TimeSlot.objects.get_or_create(
        day_of_week=TimeSlot.Day.MON,
        start_time=dt.time(8),
        end_time=dt.time(9),
        defaults={"slot_number": 1, "created_by": user, "updated_by": user},
    )
    return Schedule.objects.create(
        class_obj=class_obj,
        subject=subject,
        teacher=teacher,
        time_slot=slot,
        valid_from=valid_from,
        valid_until=valid_until,
        created_by=user,
        updated_by=user,
    )


def _make_teacher(user, registration="ACT-001", *, schedule_all=True, role=None):
    target = _make_user(f"act-teacher{registration}@test.com")
    if role:
        target.role = role
        target.save(update_fields=["role"])
    teacher = Teacher.objects.create(
        user=target, registration_number=registration, created_by=user, updated_by=user
    )
    teacher.subjects.set(Subject.objects.all())
    Class.objects.update(class_teacher=teacher)
    if schedule_all:
        for class_obj in Class.objects.all():
            for subject in Subject.objects.all():
                _make_schedule(user, class_obj, subject, teacher)
    return teacher


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

    def test_rejects_crossed_or_expired_schedule_combination(self, user):
        first_class = _make_class(user)
        second_class = _make_class(user, "1B")
        math = _make_subject(user)
        science = Subject.objects.create(
            name="Ciências", code="CIE-SCOPE", created_by=user, updated_by=user
        )
        teacher = _make_teacher(user, schedule_all=False)
        teacher.subjects.add(math, science)
        _make_schedule(user, first_class, math, teacher)
        _make_schedule(user, second_class, science, teacher)

        with pytest.raises(ValidationError):
            ActivityService(user=user).create_activity(
                {
                    "class_obj_id": first_class.pk,
                    "subject_id": science.pk,
                    "teacher_id": teacher.pk,
                    "title": "Combinação cruzada",
                    "due_date": dt.date(2025, 4, 10),
                    "max_score": 10,
                }
            )

        Schedule.objects.filter(class_obj=first_class, subject=math).update(
            valid_until=dt.date(2025, 4, 9)
        )
        with pytest.raises(ValidationError):
            ActivityService(user=user).create_activity(
                {
                    "class_obj_id": first_class.pk,
                    "subject_id": math.pk,
                    "teacher_id": teacher.pk,
                    "title": "Grade expirada",
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

    def test_teacher_cannot_update_another_teachers_activity(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
        owner = _make_teacher(user, role=role)
        other = _make_teacher(user, "ACT-OTHER", role=role)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": owner.pk,
                "title": "Atividade do titular",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )

        with pytest.raises(PermissionDeniedError):
            ActivityService(user=other.user).update_activity(
                activity.pk, {"title": "Alteração indevida"}
            )
        activity.refresh_from_db()

        assert activity.title == "Atividade do titular"

    def test_class_change_without_results_syncs_restores_and_deactivates_groups(self, user):
        first_class = _make_class(user)
        second_class = _make_class(user, "1B")
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        first_student = _make_student(user)
        second_student = _make_student(user, "ACT-S002")
        _enroll(user, first_student, first_class)
        _enroll(user, second_student, second_class)
        service = ActivityService(user=user)
        activity = service.create_activity(
            {
                "class_obj_id": first_class.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Atividade móvel",
                "modality": Activity.Modality.GROUP,
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        group = service.save_group(
            activity.pk, {"name": "Grupo inicial", "student_ids": [first_student.pk]}
        )

        service.update_activity(activity.pk, {"class_obj": second_class})

        assert not ActivitySubmission.objects.filter(
            activity=activity, student=first_student
        ).exists()
        assert ActivitySubmission.objects.filter(activity=activity, student=second_student).exists()
        assert not ActivityGroup.objects.filter(pk=group.pk).exists()

        service.update_activity(activity.pk, {"class_obj": first_class})

        restored = ActivitySubmission.objects.get(activity=activity, student=first_student)
        assert restored.is_active
        assert not ActivitySubmission.objects.filter(
            activity=activity, student=second_student
        ).exists()
        assert AuditLog.objects.filter(
            operation=AuditLog.Operation.RESTORE,
            model_name="ActivitySubmission",
            object_id=str(restored.pk),
        ).exists()

    def test_class_change_with_score_rolls_back(self, user):
        first_class = _make_class(user)
        second_class = _make_class(user, "1B")
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user)
        _enroll(user, student, first_class)
        service = ActivityService(user=user)
        activity = service.create_activity(
            {
                "class_obj_id": first_class.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Atividade avaliada",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        service.record_score(activity.pk, student.pk, 8, "Resultado lançado")

        with pytest.raises(BusinessRuleViolationError):
            service.update_activity(activity.pk, {"class_obj": second_class})
        activity.refresh_from_db()

        assert activity.class_obj == first_class
        assert activity.submissions.get(student=student).score == Decimal("8")


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

    def test_rejects_student_without_active_enrollment_in_current_class(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "INACTIVE-S001")
        enrollment = _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova com matrícula cancelada",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        enrollment.status = Enrollment.Status.CANCELLED
        enrollment.save(update_fields=["status"])

        with pytest.raises(ValidationError):
            ActivityService(user=user).record_score(activity.pk, student.pk, 7)


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


@pytest.mark.django_db
class TestActivityGroups:
    def test_save_group_and_apply_result(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "GROUP-001")
        s2 = _make_student(user, "GROUP-002")
        _enroll(user, s1, cls)
        _enroll(user, s2, cls)
        service = ActivityService(user=user)
        activity = service.create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Trabalho coletivo",
                "modality": Activity.Modality.GROUP,
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )

        group = service.save_group(
            activity.pk,
            {"name": "Grupo A", "student_ids": [s1.pk, s2.pk]},
        )
        service.apply_group_result(activity.pk, group.pk, 8, "Bom trabalho em equipe.")
        service.record_score(activity.pk, s2.pk, 9, "Ajuste individual.")

        assert group.memberships.count() == 2
        assert activity.submissions.get(student=s1).score == Decimal("8")
        assert activity.submissions.get(student=s2).score == Decimal("9")
        assert activity.submissions.get(student=s2).feedback == "Ajuste individual."

    def test_save_group_rejects_student_in_two_groups(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "GROUP-DUP")
        _enroll(user, student, cls)
        service = ActivityService(user=user)
        activity = service.create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Projeto",
                "modality": Activity.Modality.GROUP,
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        service.save_group(activity.pk, {"name": "Grupo A", "student_ids": [student.pk]})

        with pytest.raises(BusinessRuleViolationError):
            service.save_group(
                activity.pk,
                {"name": "Grupo B", "student_ids": [student.pk]},
            )
        assert ActivityGroupMember.objects.filter(activity=activity, student=student).count() == 1

    def test_group_result_blocks_class_change(self, user):
        first_class = _make_class(user)
        second_class = _make_class(user, "1B")
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "GROUP-RESULT")
        _enroll(user, student, first_class)
        service = ActivityService(user=user)
        activity = service.create_activity(
            {
                "class_obj_id": first_class.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Projeto avaliado",
                "modality": Activity.Modality.GROUP,
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        group = service.save_group(activity.pk, {"name": "Grupo A", "student_ids": [student.pk]})
        service.apply_group_result(activity.pk, group.pk, 9, "Resultado coletivo")

        with pytest.raises(BusinessRuleViolationError):
            service.update_activity(activity.pk, {"class_obj": second_class})
        activity.refresh_from_db()

        assert activity.class_obj == first_class
