"""Orçamentos de consultas dos resumos de frequência."""

import datetime as dt

import pytest
from django.utils import timezone

from attendance.models import AttendanceEntry, AttendanceRecord
from attendance.selectors import AttendanceSelector
from base.tests.factories import CustomUserFactory, StudentFactory, SubjectFactory
from classes.models import Class, Enrollment
from dashboard.selectors import DashboardSelector
from teachers.models import Teacher


@pytest.mark.django_db
@pytest.mark.parametrize("student_count", [1, 30])
def test_aggregate_attendance_query_count_independent_of_students(
    student_count, django_assert_num_queries
):
    teacher = Teacher.objects.create(user=CustomUserFactory(), registration_number="PERF")
    cls = Class.objects.create(name="Performance", academic_year=2026)
    record = AttendanceRecord.objects.create(
        class_obj=cls, teacher=teacher, subject=SubjectFactory(), date=timezone.localdate()
    )
    for index in range(student_count):
        student = StudentFactory()
        Enrollment.objects.create(
            student=student, class_obj=cls, academic_year=2026, enrollment_date=dt.date(2026, 1, 1)
        )
        AttendanceEntry.objects.create(
            record=record, student=student, status="ABSENT" if index % 2 else "PRESENT"
        )
    with django_assert_num_queries(2):
        result = AttendanceSelector().get_class_attendance_summary(cls.pk)
    assert len(result["summary"]) == student_count
    assert len(result["at_risk"]) == student_count // 2
    with django_assert_num_queries(2):
        assert DashboardSelector().get_students_at_risk_count() == student_count // 2
