"""Testes do ActivityService."""

import datetime as dt
from decimal import Decimal
from unittest.mock import patch

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
        start_time=dt.time(8),
        end_time=dt.time(9),
        defaults={
            "slot_number": 1,
            "shift": TimeSlot.Shift.MORNING,
            "created_by": user,
            "updated_by": user,
        },
    )
    return Schedule.objects.create(
        class_obj=class_obj,
        subject=subject,
        teacher=teacher,
        time_slot=slot,
        day_of_week=Schedule.Day.MON,
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
        academic_year=class_obj.academic_year,
        enrollment_date=dt.date.today(),
        status=status,
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
def test_academic_enrollment_syncs_draft_submissions_after_create_transfer_and_cancel(user):
    from classes.services import AcademicEnrollmentService

    source_class = _make_class(user, "Origem")
    target_class = _make_class(user, "Destino")
    subject = _make_subject(user)
    teacher = _make_teacher(user)
    student = _make_student(user)
    source_activity = ActivityService(user=user).create_activity(
        {
            "class_obj_id": source_class.pk,
            "subject_id": subject.pk,
            "teacher_id": teacher.pk,
            "title": "Atividade de origem",
            "due_date": dt.date(2025, 3, 10),
            "max_score": 10,
        }
    )
    target_activity = ActivityService(user=user).create_activity(
        {
            "class_obj_id": target_class.pk,
            "subject_id": subject.pk,
            "teacher_id": teacher.pk,
            "title": "Atividade de destino",
            "due_date": dt.date(2025, 3, 10),
            "max_score": 10,
        }
    )
    service = AcademicEnrollmentService(user=user)

    enrollment = service.create_from_application(
        student_id=student.pk,
        class_id=source_class.pk,
        academic_year=source_class.academic_year,
        tenant_schema="test_school",
    )
    assert ActivitySubmission.objects.filter(activity=source_activity, student=student).exists()

    target_enrollment = service.transfer_from_application(
        source_enrollment_id=enrollment.pk,
        target_class_id=target_class.pk,
        reason="Mudança de turma",
        tenant_schema="test_school",
    )
    assert not ActivitySubmission.objects.filter(activity=source_activity, student=student).exists()
    assert ActivitySubmission.objects.filter(activity=target_activity, student=student).exists()

    service.close_from_application(
        enrollment_id=target_enrollment.pk,
        reason="Encerramento solicitado",
        tenant_schema="test_school",
    )
    assert not ActivitySubmission.objects.filter(activity=target_activity, student=student).exists()


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
        submission = activity.submissions.get(student=student)
        service.batch_record_scores(
            activity.pk,
            [
                {
                    "student_id": student.pk,
                    "score": 8,
                    "feedback": "Resultado lançado",
                    "version": submission.version,
                }
            ],
        )

        with pytest.raises(BusinessRuleViolationError):
            service.update_activity(activity.pk, {"class_obj": second_class})
        activity.refresh_from_db()

        assert activity.class_obj == first_class
        assert activity.submissions.get(student=student).score == Decimal("8")


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
        audit_count = AuditLog.objects.filter(model_name="ActivitySubmission").count()
        result = ActivityService(user=user).batch_record_scores(
            activity.pk,
            [
                {
                    "student_id": s1.pk,
                    "score": 8,
                    "feedback": "OK",
                    "version": activity.submissions.get(student=s1).version,
                },
                {
                    "student_id": s2.pk,
                    "score": 6,
                    "feedback": "",
                    "version": activity.submissions.get(student=s2).version,
                },
            ],
        )
        assert result == {"saved": 2}
        assert activity.submissions.get(student=s1).score == Decimal("8")
        assert activity.submissions.get(student=s2).score == Decimal("6")
        assert AuditLog.objects.filter(model_name="ActivitySubmission").count() == audit_count + 2

        result = ActivityService(user=user).batch_record_scores(
            activity.pk,
            [
                {
                    "student_id": s1.pk,
                    "score": 8,
                    "feedback": "OK",
                    "version": activity.submissions.get(student=s1).version,
                },
                {
                    "student_id": s2.pk,
                    "score": 6,
                    "feedback": "",
                    "version": activity.submissions.get(student=s2).version,
                },
            ],
        )
        assert result == {"saved": 0}
        assert AuditLog.objects.filter(model_name="ActivitySubmission").count() == audit_count + 2

    def test_update_score_preserves_first_submitted_at(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "BATCH-SUBMITTED-AT")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova preservada",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        submission = activity.submissions.get(student=student)
        service = ActivityService(user=user)
        service.batch_record_scores(
            activity.pk,
            [{"student_id": student.pk, "score": 6, "feedback": "", "version": submission.version}],
        )
        submission.refresh_from_db()
        first_submitted_at = submission.submitted_at

        service.batch_record_scores(
            activity.pk,
            [
                {
                    "student_id": student.pk,
                    "score": 8,
                    "feedback": "Revisada",
                    "version": submission.version,
                }
            ],
        )
        submission.refresh_from_db()

        assert submission.submitted_at == first_submitted_at

    def test_invalid_row_rolls_back_all_scores(self, user):
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
        submission = activity.submissions.get(student=s1)
        with pytest.raises(ValidationError) as exc_info:
            ActivityService(user=user).batch_record_scores(
                activity.pk,
                [
                    {
                        "student_id": s1.pk,
                        "score": 7,
                        "feedback": "",
                        "version": submission.version,
                    },
                    {"student_id": "NOPE-XXX", "score": 5, "feedback": "", "version": 0},
                ],
            )
        submission.refresh_from_db()
        assert submission.score is None
        assert "student_id" in exc_info.value.errors["NOPE-XXX"]

    def test_rejects_feedback_without_score_without_writing(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "BATCH-FEEDBACK")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova feedback",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        submission = activity.submissions.get(student=student)
        with pytest.raises(ValidationError) as exc_info:
            ActivityService(user=user).batch_record_scores(
                activity.pk,
                [
                    {
                        "student_id": student.pk,
                        "score": "",
                        "feedback": "Comentário sem nota",
                        "version": submission.version,
                    }
                ],
            )
        submission.refresh_from_db()
        assert submission.score is None
        assert "score" in exc_info.value.errors[str(student.pk)]

    def test_rejects_stale_version_without_writing(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "BATCH-VERSION")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova concorrente",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        submission = activity.submissions.get(student=student)
        with pytest.raises(ValidationError) as exc_info:
            ActivityService(user=user).batch_record_scores(
                activity.pk,
                [
                    {
                        "student_id": student.pk,
                        "score": 5,
                        "feedback": "",
                        "version": submission.version + 1,
                    }
                ],
            )
        submission.refresh_from_db()
        assert submission.score is None
        assert "version" in exc_info.value.errors[str(student.pk)]

    @pytest.mark.parametrize("score", ["NaN", "Infinity", "-Infinity"])
    def test_rejects_non_finite_score_without_writing(self, user, score):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, f"BATCH-{score}")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova finita",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        submission = activity.submissions.get(student=student)

        with pytest.raises(ValidationError) as exc_info:
            ActivityService(user=user).batch_record_scores(
                activity.pk,
                [
                    {
                        "student_id": student.pk,
                        "score": score,
                        "feedback": "",
                        "version": submission.version,
                    }
                ],
            )

        submission.refresh_from_db()
        assert submission.score is None
        assert "score" in exc_info.value.errors[str(student.pk)]

    def test_rejects_batch_from_teacher_who_does_not_own_activity(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        owner = _make_teacher(user)
        student = _make_student(user, "BATCH-ACTOR")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": owner.pk,
                "title": "Prova protegida",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
        other_teacher = _make_teacher(user, "ACTOR-DENIED", role=role)
        submission = activity.submissions.get(student=student)

        with pytest.raises(PermissionDeniedError):
            ActivityService(user=other_teacher.user).batch_record_scores(
                activity.pk,
                [
                    {
                        "student_id": student.pk,
                        "score": 8,
                        "feedback": "",
                        "version": submission.version,
                    }
                ],
            )

        submission.refresh_from_db()
        assert submission.score is None

    def test_audit_failure_rolls_back_all_score_updates(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "BATCH-AUDIT")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Prova auditável",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        submission = activity.submissions.get(student=student)

        with patch("audit.services.AuditService.record", side_effect=RuntimeError("audit down")):
            with pytest.raises(RuntimeError, match="audit down"):
                ActivityService(user=user).batch_record_scores(
                    activity.pk,
                    [
                        {
                            "student_id": student.pk,
                            "score": 8,
                            "feedback": "",
                            "version": submission.version,
                        }
                    ],
                )

        submission.refresh_from_db()
        assert submission.score is None
        assert submission.version == 0


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
        submission = activity.submissions.get(student=s2)
        service.batch_record_scores(
            activity.pk,
            [
                {
                    "student_id": s2.pk,
                    "score": 9,
                    "feedback": "Ajuste individual.",
                    "version": submission.version,
                }
            ],
        )

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

    def test_apply_group_result_rolls_back_when_member_has_no_submission(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "GROUP-MISSING-SUBMISSION")
        _enroll(user, student, cls)
        service = ActivityService(user=user)
        activity = service.create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Grupo íntegro",
                "modality": Activity.Modality.GROUP,
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        group = service.save_group(activity.pk, {"name": "Grupo A", "student_ids": [student.pk]})
        activity.submissions.get(student=student).soft_delete(user=user)

        with pytest.raises(BusinessRuleViolationError):
            service.apply_group_result(activity.pk, group.pk, 8, "Resultado")

        group.refresh_from_db()
        assert group.score is None

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


@pytest.mark.django_db
class TestActivityScoreStatus:
    @pytest.mark.parametrize("method_name", ["launch_scores", "reopen_scores"])
    def test_score_status_commands_reject_user_without_edit_access(self, user, method_name):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Acesso restrito",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        finance_role, _ = Role.objects.get_or_create(name=Role.Name.FINANCE)
        finance_user = _make_user("activity-finance@test.com")
        finance_user.role = finance_role
        finance_user.save(update_fields=["role"])
        audit_count = AuditLog.objects.filter(
            model_name="Activity", object_id=str(activity.pk)
        ).count()
        arguments = (activity.pk, activity.version)
        if method_name == "reopen_scores":
            arguments += ("Correção autorizada.",)

        with pytest.raises(PermissionDeniedError):
            getattr(ActivityService(user=finance_user), method_name)(*arguments)

        activity.refresh_from_db()
        assert activity.score_status == Activity.ScoreStatus.DRAFT
        assert (
            AuditLog.objects.filter(model_name="Activity", object_id=str(activity.pk)).count()
            == audit_count
        )

    @pytest.mark.parametrize("method_name", ["launch_scores", "reopen_scores"])
    def test_score_status_commands_reject_teacher_outside_activity_scope(self, user, method_name):
        cls = _make_class(user)
        subject = _make_subject(user)
        owner = _make_teacher(user)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": owner.pk,
                "title": "Escopo de lançamento",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        teacher_role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
        outsider = _make_teacher(user, "OFFICIAL-OUTSIDER", role=teacher_role)
        audit_count = AuditLog.objects.filter(
            model_name="Activity", object_id=str(activity.pk)
        ).count()
        arguments = (activity.pk, activity.version)
        if method_name == "reopen_scores":
            arguments += ("Correção autorizada.",)

        with pytest.raises(PermissionDeniedError):
            getattr(ActivityService(user=outsider.user), method_name)(*arguments)

        assert (
            AuditLog.objects.filter(model_name="Activity", object_id=str(activity.pk)).count()
            == audit_count
        )

    def test_launch_scores_makes_grade_official_and_audits_transition(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "OFFICIAL-ZERO")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Notas oficiais",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        submission = activity.submissions.get(student=student)
        ActivityService(user=user).batch_record_scores(
            activity.pk,
            [
                {
                    "student_id": student.pk,
                    "score": 0,
                    "feedback": "",
                    "version": submission.version,
                }
            ],
        )
        activity.refresh_from_db()

        launched = ActivityService(user=user).launch_scores(activity.pk, activity.version)

        assert launched.score_status == Activity.ScoreStatus.LAUNCHED
        assert launched.scores_launched_at is not None
        assert AuditLog.objects.filter(
            model_name="Activity",
            object_id=str(activity.pk),
            old_values__score_status=Activity.ScoreStatus.DRAFT,
        ).exists()
        with pytest.raises(BusinessRuleViolationError, match="Reabra-as"):
            ActivityService(user=user).update_activity(launched.pk, {"title": "Alteração"})

    def test_launch_scores_rejects_pending_or_invalid_active_submissions(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "OFFICIAL-PENDING")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Lançamento incompleto",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )

        with pytest.raises(BusinessRuleViolationError):
            ActivityService(user=user).launch_scores(activity.pk, activity.version)

        activity.refresh_from_db()
        assert activity.score_status == Activity.ScoreStatus.DRAFT
        assert activity.scores_launched_at is None

        submission = activity.submissions.get(student=student)
        submission.score = Decimal("11.00")
        submission.save(update_fields=["score"])
        with pytest.raises(BusinessRuleViolationError):
            ActivityService(user=user).launch_scores(activity.pk, activity.version)

        activity.refresh_from_db()
        assert activity.score_status == Activity.ScoreStatus.DRAFT

    def test_launch_scores_rejects_activity_without_active_enrollments(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Atividade sem alunos",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )

        with pytest.raises(BusinessRuleViolationError):
            ActivityService(user=user).launch_scores(activity.pk, activity.version)

        activity.refresh_from_db()
        assert activity.score_status == Activity.ScoreStatus.DRAFT
        assert activity.scores_launched_at is None

    def test_launch_scores_rejects_stale_activity_version(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "OFFICIAL-STALE")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Conflito de lançamento",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        submission = activity.submissions.get(student=student)
        ActivityService(user=user).batch_record_scores(
            activity.pk,
            [
                {
                    "student_id": student.pk,
                    "score": 7,
                    "feedback": "",
                    "version": submission.version,
                }
            ],
        )
        activity.refresh_from_db()

        with pytest.raises(BusinessRuleViolationError):
            ActivityService(user=user).launch_scores(activity.pk, activity.version + 1)

        activity.refresh_from_db()
        assert activity.score_status == Activity.ScoreStatus.DRAFT

    def test_reopen_scores_requires_reason_and_restores_draft(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "OFFICIAL-REOPEN")
        _enroll(user, student, cls)
        activity = ActivityService(user=user).create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Reabertura de notas",
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        service = ActivityService(user=user)
        submission = activity.submissions.get(student=student)
        service.batch_record_scores(
            activity.pk,
            [
                {
                    "student_id": student.pk,
                    "score": 7,
                    "feedback": "",
                    "version": submission.version,
                }
            ],
        )
        activity.refresh_from_db()
        launched = service.launch_scores(activity.pk, activity.version)

        with pytest.raises(ValidationError) as exc_info:
            service.reopen_scores(launched.pk, launched.version, "")
        assert "reason" in exc_info.value.errors

        reopened = service.reopen_scores(launched.pk, launched.version, "Correção de lançamento.")

        assert reopened.score_status == Activity.ScoreStatus.DRAFT
        assert reopened.scores_launched_at is None
        audit_entry = AuditLog.objects.filter(
            model_name="Activity", object_id=str(activity.pk), operation=AuditLog.Operation.UPDATE
        ).first()
        assert audit_entry is not None
        assert audit_entry.new_values["reason"] == "[REDACTED]"
        assert audit_entry.new_values["score_status"] == Activity.ScoreStatus.DRAFT

    def test_official_scores_block_individual_and_group_mutations(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        student = _make_student(user, "OFFICIAL-GROUP")
        _enroll(user, student, cls)
        service = ActivityService(user=user)
        activity = service.create_activity(
            {
                "class_obj_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Grupo oficial",
                "modality": Activity.Modality.GROUP,
                "due_date": dt.date(2025, 4, 10),
                "max_score": 10,
            }
        )
        group = service.save_group(activity.pk, {"name": "Equipe", "student_ids": [student.pk]})
        submission = activity.submissions.get(student=student)
        service.batch_record_scores(
            activity.pk,
            [
                {
                    "student_id": student.pk,
                    "score": 8,
                    "feedback": "",
                    "version": submission.version,
                }
            ],
        )
        activity.refresh_from_db()
        launched = service.launch_scores(activity.pk, activity.version)
        submission.refresh_from_db()

        with pytest.raises(BusinessRuleViolationError):
            service.batch_record_scores(
                launched.pk,
                [
                    {
                        "student_id": student.pk,
                        "score": 8,
                        "feedback": "",
                        "version": submission.version,
                    }
                ],
            )
        with pytest.raises(BusinessRuleViolationError):
            service.apply_group_result(launched.pk, group.pk, 8)
        with pytest.raises(BusinessRuleViolationError):
            service.deactivate_group(launched.pk, group.pk)

        submission.refresh_from_db()
        group.refresh_from_db()
        assert submission.score == Decimal("8")
        assert group.is_active
