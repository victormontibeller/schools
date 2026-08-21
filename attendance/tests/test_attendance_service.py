"""Testes do AttendanceService."""

import datetime as dt

import pytest

from agenda.models import Schedule, TimeSlot
from attendance.models import AttendanceEntry, AttendanceJustification
from attendance.services import AttendanceService
from audit.models import AuditLog
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from classes.models import Class, Enrollment
from core.models import CustomUser, Role, RoleModuleAccess
from guardians.models import Guardian, StudentGuardian
from students.models import Student
from students.selectors import StudentSelector
from teachers.models import Subject, Teacher


def _make_user(email="att@test.com"):
    return CustomUser.objects.create_user(
        email=email, password="Senha123", first_name="Prof", last_name="Attendance"
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


def _make_teacher(user, registration="ATT-001", *, schedule_all=True):
    target = _make_user(f"att-teacher{registration}@test.com")
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


def _make_student(user, enrollment_number="ATT-S001"):
    return Student.objects.create(
        first_name="Maria",
        last_name="Souza",
        birth_date=dt.date(2010, 5, 15),
        enrollment_number=enrollment_number,
        created_by=user,
        updated_by=user,
    )


def _make_guardian_actor(user, suffix="SCOPE"):
    role, _ = Role.objects.get_or_create(name=Role.Name.GUARDIAN)
    actor = CustomUser.objects.create_user(
        email=f"guardian-{suffix.lower()}@attendance.test",
        password="Senha123",
        role=role,
    )
    guardian = Guardian.objects.create(
        user=actor,
        first_name="Responsável",
        created_by=user,
        updated_by=user,
    )
    return actor, guardian


def _set_teacher_attendance_access(user, teacher, *, can_create):
    role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
    RoleModuleAccess.objects.update_or_create(
        role=role,
        module_key="attendance",
        defaults={
            "can_view": True,
            "can_create": can_create,
            "can_edit": True,
            "created_by": user,
            "updated_by": user,
        },
    )
    teacher.user.role = role
    teacher.user.save(update_fields=["role", "updated_at"])


def _make_role_actor(user, role_name, suffix, *, can_view=True, can_edit=True):
    role, _ = Role.objects.get_or_create(name=role_name)
    RoleModuleAccess.objects.update_or_create(
        role=role,
        module_key="attendance",
        defaults={
            "can_view": can_view,
            "can_edit": can_edit,
            "created_by": user,
            "updated_by": user,
        },
    )
    return CustomUser.objects.create_user(
        email=f"{role_name.lower()}-{suffix}@attendance.test",
        password="Senha123",
        role=role,
    )


def _justification_payload(student):
    return {
        "student_id": student.pk,
        "start_date": dt.date(2026, 7, 10),
        "end_date": dt.date(2026, 7, 11),
        "reason": "Consulta",
    }


def _assert_justification_denied_without_write(actor, student):
    audit_count = AuditLog.objects.count()
    with pytest.raises(PermissionDeniedError):
        AttendanceService(user=actor).submit_justification(_justification_payload(student))
    assert not AttendanceJustification.objects.filter(student=student).exists()
    assert AuditLog.objects.count() == audit_count


def _enroll(user, cls, student, *, status=Enrollment.Status.ACTIVE):
    return Enrollment.objects.create(
        student=student,
        class_obj=cls,
        academic_year=cls.academic_year,
        enrollment_date=dt.date.today(),
        status=status,
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
class TestOpenAttendance:
    def test_success(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "OPEN-001")
        s2 = _make_student(user, "OPEN-002")
        _enroll(user, cls, s1)
        _enroll(user, cls, s2)
        record = AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
                "lesson_number": 1,
            }
        )
        assert record.pk is not None
        assert record.entries.count() == 2
        for entry in record.entries.all():
            assert entry.status == AttendanceEntry.Status.PRESENT

    def test_duplicate_record(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        with pytest.raises(BusinessRuleViolationError):
            AttendanceService(user=user).open_attendance(
                {
                    "class_id": cls.pk,
                    "subject_id": subject.pk,
                    "teacher_id": teacher.pk,
                    "date": dt.date(2025, 4, 10),
                }
            )

    def test_missing_required(self, user):
        with pytest.raises(ValidationError):
            AttendanceService(user=user).open_attendance({})

    def test_teacher_requires_lesson_content(self, user):
        role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
        teacher_user = CustomUser.objects.create_user(
            email="attendance-scope@test.com",
            password="Senha123",
            role=role,
        )
        teacher = Teacher.objects.create(
            user=teacher_user,
            registration_number="ATT-SCOPE",
            created_by=user,
            updated_by=user,
        )
        cls = _make_class(user)
        cls.class_teacher = teacher
        cls.save(update_fields=["class_teacher"])
        subject = _make_subject(user)
        teacher.subjects.add(subject)

        with pytest.raises(ValidationError) as exc_info:
            AttendanceService(user=teacher_user).open_attendance(
                {
                    "class_id": cls.pk,
                    "subject_id": subject.pk,
                    "teacher_id": teacher.pk,
                    "date": dt.date(2025, 4, 10),
                }
            )

        assert "lesson_content" in exc_info.value.errors

    def test_rejects_crossed_schedule_combination_for_class_teacher(self, user):
        first_class = _make_class(user)
        second_class = _make_class(user, "1B")
        math = _make_subject(user)
        science = Subject.objects.create(
            name="Ciências", code="CIE-ATT-SCOPE", created_by=user, updated_by=user
        )
        teacher = _make_teacher(user, schedule_all=False)
        teacher.subjects.add(math, science)
        _make_schedule(user, first_class, math, teacher)
        _make_schedule(user, second_class, science, teacher)

        with pytest.raises(ValidationError) as exc_info:
            AttendanceService(user=user).open_attendance(
                {
                    "class_id": first_class.pk,
                    "subject_id": science.pk,
                    "teacher_id": teacher.pk,
                    "date": dt.date(2025, 4, 10),
                    "lesson_content": "Conteúdo",
                }
            )

        assert "class_obj" in exc_info.value.errors

    def test_rejects_schedule_outside_attendance_date(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user, schedule_all=False)
        _make_schedule(
            user,
            cls,
            subject,
            teacher,
            valid_from=dt.date(2025, 4, 11),
        )

        with pytest.raises(ValidationError):
            AttendanceService(user=user).open_attendance(
                {
                    "class_id": cls.pk,
                    "subject_id": subject.pk,
                    "teacher_id": teacher.pk,
                    "date": dt.date(2025, 4, 10),
                }
            )


@pytest.mark.django_db
class TestOpenAttendanceErrors:
    def test_class_not_found(self, user):
        import uuid

        subject = _make_subject(user)
        teacher = _make_teacher(user)
        with pytest.raises(ObjectNotFoundError):
            AttendanceService(user=user).open_attendance(
                {
                    "class_id": uuid.uuid4(),
                    "subject_id": subject.pk,
                    "teacher_id": teacher.pk,
                    "date": dt.date(2025, 4, 10),
                }
            )

    def test_subject_not_found(self, user):
        import uuid

        cls = _make_class(user)
        teacher = _make_teacher(user)
        with pytest.raises(ObjectNotFoundError):
            AttendanceService(user=user).open_attendance(
                {
                    "class_id": cls.pk,
                    "subject_id": uuid.uuid4(),
                    "teacher_id": teacher.pk,
                    "date": dt.date(2025, 4, 10),
                }
            )

    def test_teacher_not_found(self, user):
        import uuid

        cls = _make_class(user)
        subject = _make_subject(user)
        with pytest.raises(ObjectNotFoundError):
            AttendanceService(user=user).open_attendance(
                {
                    "class_id": cls.pk,
                    "subject_id": subject.pk,
                    "teacher_id": uuid.uuid4(),
                    "date": dt.date(2025, 4, 10),
                }
            )


@pytest.mark.django_db
class TestRecordAttendance:
    def test_success(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "REC-001")
        s2 = _make_student(user, "REC-002")
        _enroll(user, cls, s1)
        _enroll(user, cls, s2)
        record = AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        AttendanceService(user=user).record_attendance(
            record.pk,
            {
                str(s1.pk): AttendanceEntry.Status.ABSENT,
                str(s2.pk): AttendanceEntry.Status.PRESENT,
            },
        )
        entries = record.entries.all()
        assert entries.get(student=s1).status == AttendanceEntry.Status.ABSENT
        assert entries.get(student=s2).status == AttendanceEntry.Status.PRESENT

    def test_with_justification(self, user):
        from audit.models import AuditLog

        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "JUS-001")
        _enroll(user, cls, s1)
        record = AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        AttendanceService(user=user).record_attendance(
            record.pk,
            {
                str(s1.pk): {
                    "status": AttendanceEntry.Status.JUSTIFIED,
                    "justification": "Atestado médico",
                },
            },
        )
        entry = record.entries.get(student=s1)
        assert entry.status == AttendanceEntry.Status.JUSTIFIED
        assert entry.justification == "Atestado médico"
        log = AuditLog.objects.filter(
            operation=AuditLog.Operation.UPDATE,
            model_name="AttendanceEntry",
            object_id=str(entry.pk),
        ).latest("created_at")
        assert log.old_values == {
            "status": AttendanceEntry.Status.PRESENT,
            "justification": "[REDACTED]",
            "note": "[REDACTED]",
        }

    def test_invalid_status(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "INV-001")
        _enroll(user, cls, s1)
        record = AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        with pytest.raises(ValidationError):
            AttendanceService(user=user).record_attendance(record.pk, {str(s1.pk): "INVALID"})

    def test_student_not_in_record(self, user):
        import uuid

        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        record = AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        with pytest.raises(ObjectNotFoundError):
            AttendanceService(user=user).record_attendance(
                record.pk, {str(uuid.uuid4()): AttendanceEntry.Status.ABSENT}
            )

    def test_teacher_cannot_record_attendance_for_another_teacher_without_side_effects(self, user):
        cls = _make_class(user, "RECORD-OTHER-TEACHER")
        subject = _make_subject(user)
        owner = _make_teacher(user, "RECORD-OWNER")
        intruder = _make_teacher(user, "RECORD-INTRUDER", schedule_all=False)
        _set_teacher_attendance_access(user, intruder, can_create=True)
        student = _make_student(user, "RECORD-OTHER-STUDENT")
        _enroll(user, cls, student)
        record = AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": owner.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        audit_count = AuditLog.objects.count()

        with pytest.raises(PermissionDeniedError):
            AttendanceService(user=intruder.user).record_attendance(
                record.pk, {str(student.pk): AttendanceEntry.Status.ABSENT}
            )

        entry = record.entries.get(student=student)
        assert entry.status == AttendanceEntry.Status.PRESENT
        assert AuditLog.objects.count() == audit_count


@pytest.mark.django_db
class TestUpdateEntry:
    def test_success(self, user, monkeypatch):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "UPD-E001")
        _enroll(user, cls, s1)
        record = AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        entry = record.entries.get(student=s1)
        logged = {}
        service = AttendanceService(user=user)
        monkeypatch.setattr(
            service,
            "_log",
            lambda message, **extra: logged.update(message=message, **extra),
        )
        updated = service.update_entry(entry.pk, AttendanceEntry.Status.ABSENT)
        assert updated.status == AttendanceEntry.Status.ABSENT
        assert logged == {
            "message": "Lançamento individual atualizado",
            "entry_id": str(entry.pk),
            "record_id": str(record.pk),
            "status": AttendanceEntry.Status.ABSENT,
        }

    def test_teacher_cannot_update_entry_from_another_teacher_without_side_effects(self, user):
        cls = _make_class(user, "UPDATE-OTHER-TEACHER")
        subject = _make_subject(user)
        owner = _make_teacher(user, "UPDATE-OWNER")
        intruder = _make_teacher(user, "UPDATE-INTRUDER", schedule_all=False)
        _set_teacher_attendance_access(user, intruder, can_create=True)
        student = _make_student(user, "UPDATE-OTHER-STUDENT")
        _enroll(user, cls, student)
        record = AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": owner.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        entry = record.entries.get(student=student)
        audit_count = AuditLog.objects.count()

        with pytest.raises(PermissionDeniedError):
            AttendanceService(user=intruder.user).update_entry(
                entry.pk, AttendanceEntry.Status.ABSENT
            )

        entry.refresh_from_db()
        assert entry.status == AttendanceEntry.Status.PRESENT
        assert AuditLog.objects.count() == audit_count


@pytest.mark.django_db
class TestSubmitJustification:
    def test_success(self, user):
        student = _make_student(user, "JUS-A001")
        just = AttendanceService(user=user).submit_justification(
            {
                "student_id": student.pk,
                "start_date": dt.date(2025, 4, 10),
                "end_date": dt.date(2025, 4, 12),
                "reason": "Atestado médico",
            }
        )
        assert just.pk is not None
        assert just.status == AttendanceJustification.Status.PENDING

    def test_missing_required(self, user):
        with pytest.raises(ValidationError):
            AttendanceService(user=user).submit_justification({"student_id": "123"})

    def test_invalid_date_range(self, user):
        student = _make_student(user, "JUS-A002")
        with pytest.raises(ValidationError):
            AttendanceService(user=user).submit_justification(
                {
                    "student_id": student.pk,
                    "start_date": dt.date(2025, 4, 12),
                    "end_date": dt.date(2025, 4, 10),
                    "reason": "Erro",
                }
            )

    def test_guardian_with_active_custody_can_submit(self, user):
        student = _make_student(user, "JUS-GUARDIAN-OK")
        actor, guardian = _make_guardian_actor(user, "OK")
        StudentGuardian.objects.create(
            student=student,
            guardian=guardian,
            has_custody=True,
            created_by=user,
            updated_by=user,
        )

        justification = AttendanceService(user=actor).submit_justification(
            _justification_payload(student)
        )

        assert justification.student_id == student.pk

    @pytest.mark.parametrize(
        ("linked", "link_active", "has_custody", "guardian_active"),
        [
            (False, True, True, True),
            (True, False, True, True),
            (True, True, False, True),
            (True, True, True, False),
        ],
    )
    def test_guardian_outside_scope_is_denied_without_write_or_audit(
        self, user, linked, link_active, has_custody, guardian_active
    ):
        student = _make_student(
            user,
            (
                f"JUS-DENIED-{int(linked)}-{int(link_active)}-"
                f"{int(has_custody)}-{int(guardian_active)}"
            ),
        )
        actor, guardian = _make_guardian_actor(
            user,
            (
                f"DENIED-{int(linked)}-{int(link_active)}-"
                f"{int(has_custody)}-{int(guardian_active)}"
            ),
        )
        if linked:
            guardian.is_active = guardian_active
            guardian.save(update_fields=["is_active", "updated_at"])
            link = StudentGuardian.objects.create(
                student=student,
                guardian=guardian,
                has_custody=has_custody,
                created_by=user,
                updated_by=user,
            )
            if not link_active:
                link.is_active = False
                link.save(update_fields=["is_active", "updated_at"])
        _assert_justification_denied_without_write(actor, student)

    def test_missing_actor_is_denied_without_write_or_audit(self, user):
        student = _make_student(user, "JUS-NO-ACTOR")
        _assert_justification_denied_without_write(None, student)

    def test_non_guardian_without_attendance_create_is_denied(self, user):
        role, _ = Role.objects.get_or_create(name=Role.Name.SECRETARY)
        actor = CustomUser.objects.create_user(
            email="secretary-no-attendance-create@test.com",
            password="Senha123",
            role=role,
        )
        student = _make_student(user, "JUS-NO-CREATE")
        _assert_justification_denied_without_write(actor, student)

    def test_teacher_can_submit_only_for_assigned_student(self, user):
        assigned_class = _make_class(user, "TEACHER-SCOPE")
        _make_subject(user)
        teacher = _make_teacher(user, "JUS-SCOPE")
        _set_teacher_attendance_access(user, teacher, can_create=True)
        assigned_student = _make_student(user, "JUS-TEACHER-ASSIGNED")
        outsider = _make_student(user, "JUS-TEACHER-OUTSIDER")
        _enroll(user, assigned_class, assigned_student)
        outsider_class = _make_class(user, "TEACHER-OUTSIDER")
        _enroll(user, outsider_class, outsider)
        service = AttendanceService(user=teacher.user)

        justification = service.submit_justification(_justification_payload(assigned_student))

        assert justification.student_id == assigned_student.pk
        _assert_justification_denied_without_write(teacher.user, outsider)

    def test_teacher_with_assigned_student_but_without_create_is_denied(self, user):
        assigned_class = _make_class(user, "TEACHER-REVOKED")
        _make_subject(user)
        teacher = _make_teacher(user, "JUS-REVOKED")
        _set_teacher_attendance_access(user, teacher, can_create=False)
        assigned_student = _make_student(user, "JUS-TEACHER-REVOKED")
        _enroll(user, assigned_class, assigned_student)
        _assert_justification_denied_without_write(teacher.user, assigned_student)

    @pytest.mark.parametrize("status", [Enrollment.Status.TRANSFERRED, Enrollment.Status.CANCELLED])
    def test_teacher_cannot_submit_for_inactive_enrollment_without_write_or_audit(
        self, user, status
    ):
        assigned_class = _make_class(user, f"TEACHER-{status}")
        _make_subject(user)
        teacher = _make_teacher(user, f"JUS-{status}")
        _set_teacher_attendance_access(user, teacher, can_create=True)
        student = _make_student(user, f"JUS-{status}")
        _enroll(user, assigned_class, student, status=status)

        assert (
            not StudentSelector()
            .eligible_for_justification(teacher.user)
            .filter(pk=student.pk)
            .exists()
        )
        _assert_justification_denied_without_write(teacher.user, student)

    def test_teacher_cannot_submit_for_soft_deleted_active_enrollment(self, user):
        assigned_class = _make_class(user, "TEACHER-SOFT-DELETED")
        _make_subject(user)
        teacher = _make_teacher(user, "JUS-SOFT-DELETED")
        _set_teacher_attendance_access(user, teacher, can_create=True)
        student = _make_student(user, "JUS-SOFT-DELETED")
        enrollment = _enroll(user, assigned_class, student)
        enrollment.soft_delete(user=user)

        selector = StudentSelector()
        listed = selector.list_students_for_user(
            user_id=teacher.user_id,
            role_name=Role.Name.TEACHER,
        )
        assert student not in listed.items
        assert not selector.eligible_for_justification(teacher.user).filter(pk=student.pk).exists()
        _assert_justification_denied_without_write(teacher.user, student)


@pytest.mark.django_db
class TestApproveJustification:
    def test_success(self, user):
        student = _make_student(user, "APR-001")
        just = AttendanceService(user=user).submit_justification(
            {
                "student_id": student.pk,
                "start_date": dt.date(2025, 4, 10),
                "end_date": dt.date(2025, 4, 12),
                "reason": "Atestado",
            }
        )
        result = AttendanceService(user=user).approve_justification(just.pk)
        assert result.status == AttendanceJustification.Status.APPROVED
        assert result.approved_by == user
        assert result.approved_at is not None

    def test_already_processed(self, user):
        student = _make_student(user, "APR-002")
        just = AttendanceService(user=user).submit_justification(
            {
                "student_id": student.pk,
                "start_date": dt.date(2025, 4, 10),
                "end_date": dt.date(2025, 4, 12),
                "reason": "Atestado",
            }
        )
        AttendanceService(user=user).approve_justification(just.pk)
        with pytest.raises(BusinessRuleViolationError):
            AttendanceService(user=user).approve_justification(just.pk)

    def test_coordinator_with_edit_access_can_approve(self, user):
        actor = _make_role_actor(user, Role.Name.COORDINATOR, "approve")
        student = _make_student(user, "APR-COORDINATOR")
        just = AttendanceService(user=user).submit_justification(_justification_payload(student))

        result = AttendanceService(user=actor).approve_justification(just.pk)

        assert result.status == AttendanceJustification.Status.APPROVED
        assert result.approved_by == actor

    @pytest.mark.parametrize("command", ["approve", "reject"])
    def test_decision_reads_justification_with_select_for_update(self, user, monkeypatch, command):
        student = _make_student(user, f"LOCK-{command.upper()}")
        just = AttendanceService(user=user).submit_justification(_justification_payload(student))
        locked_get_calls = []

        class LockedQuerySet:
            def get(self, **kwargs):
                locked_get_calls.append(kwargs)
                return just

        lock_calls = []

        def select_for_update():
            lock_calls.append(True)
            return LockedQuerySet()

        monkeypatch.setattr(
            AttendanceJustification.objects,
            "select_for_update",
            select_for_update,
        )

        service = AttendanceService(user=user)
        if command == "approve":
            service.approve_justification(just.pk)
        else:
            service.reject_justification(just.pk, "Documento insuficiente")

        assert lock_calls == [True]
        assert locked_get_calls == [{"pk": just.pk}]

    @pytest.mark.parametrize("role_name", [Role.Name.TEACHER, Role.Name.SECRETARY])
    def test_ineligible_role_cannot_approve_without_write_or_audit(self, user, role_name):
        actor = _make_role_actor(user, role_name, f"approve-{role_name.lower()}")
        student = _make_student(user, f"APR-DENIED-{role_name}")
        just = AttendanceService(user=user).submit_justification(_justification_payload(student))
        audit_count = AuditLog.objects.count()

        with pytest.raises(PermissionDeniedError):
            AttendanceService(user=actor).approve_justification(just.pk)

        just.refresh_from_db()
        assert just.status == AttendanceJustification.Status.PENDING
        assert AuditLog.objects.count() == audit_count


@pytest.mark.django_db
class TestRejectJustification:
    def test_success(self, user):
        student = _make_student(user, "REJ-001")
        just = AttendanceService(user=user).submit_justification(
            {
                "student_id": student.pk,
                "start_date": dt.date(2025, 4, 10),
                "end_date": dt.date(2025, 4, 12),
                "reason": "Atestado",
            }
        )
        result = AttendanceService(user=user).reject_justification(just.pk, "Motivo insuficiente")
        assert result.status == AttendanceJustification.Status.REJECTED
        assert result.rejection_reason == "Motivo insuficiente"

    def test_already_processed(self, user):
        student = _make_student(user, "REJ-002")
        just = AttendanceService(user=user).submit_justification(
            {
                "student_id": student.pk,
                "start_date": dt.date(2025, 4, 10),
                "end_date": dt.date(2025, 4, 12),
                "reason": "Atestado",
            }
        )
        AttendanceService(user=user).reject_justification(just.pk)
        with pytest.raises(BusinessRuleViolationError):
            AttendanceService(user=user).reject_justification(just.pk)

    def test_teacher_cannot_reject_without_write_or_audit(self, user):
        actor = _make_role_actor(user, Role.Name.TEACHER, "reject")
        student = _make_student(user, "REJ-DENIED-TEACHER")
        just = AttendanceService(user=user).submit_justification(_justification_payload(student))
        audit_count = AuditLog.objects.count()

        with pytest.raises(PermissionDeniedError):
            AttendanceService(user=actor).reject_justification(just.pk, "Não deve persistir")

        just.refresh_from_db()
        assert just.status == AttendanceJustification.Status.PENDING
        assert just.rejection_reason == ""
        assert AuditLog.objects.count() == audit_count

    def test_coordinator_without_edit_access_cannot_reject_without_write_or_audit(self, user):
        actor = _make_role_actor(
            user,
            Role.Name.COORDINATOR,
            "reject-revoked",
            can_edit=False,
        )
        student = _make_student(user, "REJ-COORDINATOR-REVOKED")
        just = AttendanceService(user=user).submit_justification(_justification_payload(student))
        audit_count = AuditLog.objects.count()

        with pytest.raises(PermissionDeniedError):
            AttendanceService(user=actor).reject_justification(just.pk, "Não deve persistir")

        just.refresh_from_db()
        assert just.status == AttendanceJustification.Status.PENDING
        assert just.rejection_reason == ""
        assert AuditLog.objects.count() == audit_count


@pytest.mark.django_db
class TestCalculateAttendance:
    def test_full_attendance(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "CALC-001")
        _enroll(user, cls, s1)
        AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        rate = AttendanceService(user=user).calculate_attendance_rate(s1.pk, cls.pk)
        assert rate == 100.0

    def test_partial_attendance(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "CALC-002")
        _enroll(user, cls, s1)
        record = AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        # Mark as absent
        entry = record.entries.get(student=s1)
        entry.status = AttendanceEntry.Status.ABSENT
        entry.save()
        rate = AttendanceService(user=user).calculate_attendance_rate(s1.pk, cls.pk)
        assert rate == 0.0

    def test_justified_counts_as_present(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "CALC-003")
        _enroll(user, cls, s1)
        record = AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        entry = record.entries.get(student=s1)
        entry.status = AttendanceEntry.Status.JUSTIFIED
        entry.save()
        rate = AttendanceService(user=user).calculate_attendance_rate(s1.pk, cls.pk)
        assert rate == 100.0

    def test_no_records(self, user):
        student = _make_student(user, "CALC-004")
        rate = AttendanceService(user=user).calculate_attendance_rate(
            student.pk, "00000000-0000-0000-0000-000000000000"
        )
        assert rate is None

    def test_entry_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            AttendanceService(user=user).update_entry(uuid.uuid4(), AttendanceEntry.Status.ABSENT)

    def test_submit_justification_student_not_found(self, user):
        import uuid

        with pytest.raises(ValidationError):
            AttendanceService(user=user).submit_justification(
                {
                    "student_id": uuid.uuid4(),
                    "start_date": dt.date(2025, 4, 10),
                    "end_date": dt.date(2025, 4, 12),
                    "reason": "Atestado",
                }
            )

    def test_update_entry_justified(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "UPD-JUS")
        _enroll(user, cls, s1)
        record = AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        entry = record.entries.get(student=s1)
        updated = AttendanceService(user=user).update_entry(
            entry.pk, AttendanceEntry.Status.JUSTIFIED, "Atestado"
        )
        assert updated.status == AttendanceEntry.Status.JUSTIFIED
        assert updated.justification == "Atestado"

    def test_threshold_unknown(self, user):
        student = _make_student(user, "THR-UNK")
        result = AttendanceService(user=user).get_attendance_threshold(
            student.pk, "00000000-0000-0000-0000-000000000000"
        )
        assert result["level"] == "UNKNOWN"
        assert result["rate"] is None

    def test_threshold_critical(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "THR-CRIT")
        _enroll(user, cls, s1)
        for i in range(4):
            record = AttendanceService(user=user).open_attendance(
                {
                    "class_id": cls.pk,
                    "subject_id": subject.pk,
                    "teacher_id": teacher.pk,
                    "date": dt.date(2025, 4, 10) + dt.timedelta(days=i),
                }
            )
            entry = record.entries.get(student=s1)
            if i >= 1:
                entry.status = AttendanceEntry.Status.ABSENT
                entry.save()
        result = AttendanceService(user=user).get_attendance_threshold(s1.pk, cls.pk)
        assert result["rate"] == 25.0
        assert result["level"] == "CRITICAL"

    def test_threshold_alert(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "THR-AL")
        _enroll(user, cls, s1)
        for i in range(3):
            record = AttendanceService(user=user).open_attendance(
                {
                    "class_id": cls.pk,
                    "subject_id": subject.pk,
                    "teacher_id": teacher.pk,
                    "date": dt.date(2025, 4, 10) + dt.timedelta(days=i),
                }
            )
            entry = record.entries.get(student=s1)
            if i == 0:
                entry.status = AttendanceEntry.Status.ABSENT
                entry.save()
        result = AttendanceService(user=user).get_attendance_threshold(s1.pk, cls.pk)
        assert result["level"] == "ALERT"

    def test_threshold_ok(self, user):
        cls = _make_class(user)
        subject = _make_subject(user)
        teacher = _make_teacher(user)
        s1 = _make_student(user, "THR-001")
        _enroll(user, cls, s1)
        AttendanceService(user=user).open_attendance(
            {
                "class_id": cls.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "date": dt.date(2025, 4, 10),
            }
        )
        result = AttendanceService(user=user).get_attendance_threshold(s1.pk, cls.pk)
        assert result["level"] == "OK"
        assert result["rate"] == 100.0
