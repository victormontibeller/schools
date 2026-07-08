"""Testes do AttendanceService."""

import datetime as dt

import pytest

from attendance.models import AttendanceEntry, AttendanceJustification
from attendance.services import AttendanceService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from classes.models import Class, Enrollment
from core.models import CustomUser
from students.models import Student
from teachers.models import Subject, Teacher


def _make_user(email="att@test.com"):
    return CustomUser.objects.create_user(
        email=email, password="Senha123", first_name="Prof", last_name="Attendance"
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


def _make_teacher(user, registration="ATT-001"):
    target = _make_user(f"att-teacher{registration}@test.com")
    return Teacher.objects.create(
        user=target, registration_number=registration, created_by=user, updated_by=user
    )


def _make_student(user, enrollment_number="ATT-S001"):
    return Student.objects.create(
        first_name="Maria",
        last_name="Souza",
        birth_date=dt.date(2010, 5, 15),
        enrollment_number=enrollment_number,
        created_by=user,
        updated_by=user,
    )


def _enroll(user, cls, student):
    return Enrollment.objects.create(
        student=student,
        class_obj=cls,
        enrollment_date=dt.date.today(),
        status=Enrollment.Status.ACTIVE,
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
            "justification": "",
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


@pytest.mark.django_db
class TestUpdateEntry:
    def test_success(self, user):
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
        updated = AttendanceService(user=user).update_entry(entry.pk, AttendanceEntry.Status.ABSENT)
        assert updated.status == AttendanceEntry.Status.ABSENT


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
