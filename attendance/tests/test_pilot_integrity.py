"""Isolamento docente e concorrência na chamada do piloto."""

import datetime as dt

import pytest

from attendance.models import AttendanceEntry
from attendance.selectors import AttendanceSelector
from attendance.services import AttendanceService
from attendance.tests.test_attendance_service import (
    _enroll,
    _make_class,
    _make_student,
    _make_subject,
    _make_teacher,
)
from audit.models import AuditLog
from base.exceptions import BusinessRuleViolationError, PermissionDeniedError
from core.access_selectors import ObjectAccessSelector
from core.models import CustomUser, Role

pytestmark = pytest.mark.django_db


def _record(user):
    cls = _make_class(user)
    subject = _make_subject(user)
    teacher = _make_teacher(user)
    students = [_make_student(user, "PILOT-1"), _make_student(user, "PILOT-2")]
    for student in students:
        _enroll(user, cls, student)
    record = AttendanceService(user=user).open_attendance(
        {
            "class_id": cls.pk,
            "subject_id": subject.pk,
            "teacher_id": teacher.pk,
            "date": dt.date(2025, 4, 10),
        }
    )
    return record, teacher


def test_record_rejects_stale_batch_and_rolls_back_other_entries(user):
    record, _ = _record(user)
    first, second = list(record.entries.order_by("pk"))
    stale = second.version
    second.note = "Alteração concorrente"
    second.save()
    audit_count = AuditLog.objects.count()
    with pytest.raises(BusinessRuleViolationError):
        AttendanceService(user=user).record_attendance(
            record.pk,
            {
                str(first.student_id): {"status": "ABSENT", "version": first.version},
                str(second.student_id): {"status": "ABSENT", "version": stale},
            },
        )
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == AttendanceEntry.Status.PRESENT
    assert second.note == "Alteração concorrente"
    assert AuditLog.objects.count() == audit_count


def test_list_denies_teacher_without_profile_and_risk_class(user):
    record, _ = _record(user)
    role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
    teacher = CustomUser.objects.create_user(email="missing@example.test", role=role)
    assert not AttendanceSelector().list_records(user=teacher).total
    with pytest.raises(PermissionDeniedError):
        AttendanceSelector().risk_context(teacher, str(record.class_obj_id))


def test_access_revokes_when_teacher_profile_is_deactivated(user):
    record, teacher = _record(user)
    assert ObjectAccessSelector().teacher_can_access_attendance(teacher.user_id, record.pk)
    teacher.is_active = False
    teacher.save()
    assert not ObjectAccessSelector().teacher_can_access_attendance(teacher.user_id, record.pk)
