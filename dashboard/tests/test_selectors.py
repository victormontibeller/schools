"""Testes do DashboardSelector."""

import pytest

from dashboard.selectors import DashboardSelector


@pytest.mark.django_db
class TestSchoolKPIs:
    def test_total_students_zero(self, user):
        assert DashboardSelector().get_total_students() == 0

    def test_total_students_with_data(self, user):
        from students.models import Student

        Student.objects.create(
            first_name="Test",
            last_name="Student",
            birth_date="2010-01-01",
            enrollment_number="DS001",
            created_by=user,
            updated_by=user,
        )
        assert DashboardSelector().get_total_students() == 1

    def test_total_teachers(self, user):
        from core.models import CustomUser
        from teachers.models import Teacher

        target = CustomUser.objects.create_user(
            email="ds-teacher@test.com",
            password="Senha123",
            first_name="Prof",
            last_name="Dash",
        )
        Teacher.objects.create(
            user=target,
            registration_number="DS-T001",
            created_by=user,
            updated_by=user,
        )
        assert DashboardSelector().get_total_teachers() == 1

    def test_total_classes(self, user):
        from classes.models import Class

        Class.objects.create(
            name="DS-1A",
            grade="1o Ano",
            academic_year=2025,
            shift=Class.Shift.MORNING,
            created_by=user,
            updated_by=user,
        )
        assert DashboardSelector().get_total_classes() == 1

    def test_total_guardians(self, user):
        from core.models import CustomUser
        from guardians.models import Guardian

        target = CustomUser.objects.create_user(
            email="ds-guardian@test.com",
            password="Senha123",
            first_name="Resp",
            last_name="Dash",
        )
        Guardian.objects.create(
            user=target,
            relationship_type="PAI",
            created_by=user,
            updated_by=user,
        )
        assert DashboardSelector().get_total_guardians() == 1

    def test_today_attendance_empty(self, user):
        assert DashboardSelector().get_today_attendance_rate() is None

    def test_weekly_attendance_empty(self, user):
        result = DashboardSelector().get_weekly_attendance()
        assert len(result) == 7

    def test_students_at_risk_zero(self, user):
        assert DashboardSelector().get_students_at_risk_count() == 0

    def test_pending_activities_empty(self, user):
        assert DashboardSelector().get_pending_activities() == []

    def test_upcoming_events_empty(self, user):
        assert DashboardSelector().get_upcoming_events() == []

    def test_recent_announcements_empty(self, user):
        assert DashboardSelector().get_recent_announcements() == []
