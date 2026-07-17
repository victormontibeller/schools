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
            grade=Class.Grade.ELEMENTARY_1,
            education_stage=Class.EducationStage.ELEMENTARY_I,
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

    def test_diary_kpis_measure_latest_publication_views(self, user, monkeypatch):
        from student_diary.tests.test_workflow import _guardian, _saved_sheet
        from student_diary.workflow_services import DiaryWorkflowService

        sheet, student = _saved_sheet(user, user)
        guardian = _guardian(user, student, suffix="dashboard")
        monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)
        workflow = DiaryWorkflowService(user=user)
        workflow.submit_sheet(sheet.pk)
        entry = workflow.approve_sheet(sheet.pk).entries.get()

        before_view = DashboardSelector().get_diary_kpis(user)
        DiaryWorkflowService(user=guardian.user).mark_entry_viewed(entry.pk)
        after_view = DashboardSelector().get_diary_kpis(user)

        assert before_view["view_rate_24h"] == 0.0
        assert after_view["view_rate_24h"] == 100.0
        assert after_view["approval_median_hours"] is not None

    def test_diary_kpis_show_guardian_unread_count(self, user, monkeypatch):
        from student_diary.tests.test_workflow import _guardian, _saved_sheet
        from student_diary.workflow_services import DiaryWorkflowService

        sheet, student = _saved_sheet(user, user)
        guardian = _guardian(user, student, suffix="guardian-dashboard")
        monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)
        workflow = DiaryWorkflowService(user=user)
        workflow.submit_sheet(sheet.pk)
        workflow.approve_sheet(sheet.pk)

        result = DashboardSelector().get_diary_kpis(guardian.user)

        assert result == {"role": "GUARDIAN", "unread": 1, "published": 1}
