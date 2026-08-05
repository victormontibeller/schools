"""Testes do DashboardSelector."""

import pytest
from django.utils import timezone

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

    def test_guardian_school_kpis_only_include_custodial_students_and_active_classes(self, user):
        import datetime as dt

        from academic_calendar.models import CalendarEvent
        from activities.models import Activity
        from activities.tests.test_views import _group_activity
        from attendance.models import AttendanceEntry, AttendanceRecord
        from classes.models import Class, Enrollment
        from core.models import CustomUser, Role
        from guardians.models import Guardian, StudentGuardian
        from notifications.models import Announcement
        from students.models import Student
        from teachers.models import Subject, Teacher

        own_activity, _group, child = _group_activity(user)
        own_activity.title = "Atividade do filho"
        own_activity.due_date = timezone.localdate() + dt.timedelta(days=1)
        own_activity.save(update_fields=["title", "due_date"])
        other_class = Class.objects.create(
            name="Turma externa",
            grade=Class.Grade.ELEMENTARY_4,
            education_stage=Class.EducationStage.ELEMENTARY_I,
            academic_year=2026,
            created_by=user,
            updated_by=user,
        )
        outsider = Student.objects.create(
            first_name="Aluno",
            last_name="Externo",
            birth_date=dt.date(2014, 2, 1),
            enrollment_number="DASH-OUTSIDER",
            created_by=user,
            updated_by=user,
        )
        Enrollment.objects.create(
            class_obj=other_class,
            student=outsider,
            academic_year=2026,
            enrollment_date=dt.date(2026, 1, 20),
            status=Enrollment.Status.ACTIVE,
            created_by=user,
            updated_by=user,
        )
        subject = Subject.objects.create(
            name="Ciências dashboard",
            code="DASH-CIE",
            created_by=user,
            updated_by=user,
        )
        teacher_user = CustomUser.objects.create_user(
            email="teacher-dashboard-scope@test.com", password="Senha123"
        )
        teacher = Teacher.objects.create(
            user=teacher_user,
            registration_number="DASH-SCOPE-TEACHER",
            created_by=user,
            updated_by=user,
        )
        Activity.objects.create(
            class_obj=other_class,
            subject=subject,
            teacher=teacher,
            title="Atividade externa",
            due_date=timezone.localdate() + dt.timedelta(days=1),
            created_by=user,
            updated_by=user,
        )
        own_record = AttendanceRecord.objects.create(
            class_obj=own_activity.class_obj,
            subject=own_activity.subject,
            teacher=own_activity.teacher,
            date=timezone.localdate(),
            lesson_content="Conteúdo próprio",
            created_by=user,
            updated_by=user,
        )
        AttendanceEntry.objects.create(
            record=own_record,
            student=child,
            status=AttendanceEntry.Status.PRESENT,
            created_by=user,
            updated_by=user,
        )
        other_record = AttendanceRecord.objects.create(
            class_obj=other_class,
            subject=subject,
            teacher=teacher,
            date=timezone.localdate(),
            lesson_content="Conteúdo externo",
            created_by=user,
            updated_by=user,
        )
        AttendanceEntry.objects.create(
            record=other_record,
            student=outsider,
            status=AttendanceEntry.Status.ABSENT,
            created_by=user,
            updated_by=user,
        )
        role = Role.objects.get(name=Role.Name.GUARDIAN)
        guardian_user = CustomUser.objects.create_user(
            email="guardian-dashboard-scope@test.com", password="Senha123", role=role
        )
        guardian = Guardian.objects.create(
            user=guardian_user,
            first_name="Responsável",
            created_by=user,
            updated_by=user,
        )
        StudentGuardian.objects.create(
            guardian=guardian,
            student=child,
            has_custody=True,
            created_by=user,
            updated_by=user,
        )
        own_event = CalendarEvent.objects.create(
            title="Evento do filho",
            start_date=timezone.localdate() + dt.timedelta(days=1),
            end_date=timezone.localdate() + dt.timedelta(days=1),
            audience=CalendarEvent.Audience.CLASS,
            class_obj=own_activity.class_obj,
            is_public=True,
            created_by=user,
            updated_by=user,
        )
        CalendarEvent.objects.create(
            title="Evento externo",
            start_date=timezone.localdate() + dt.timedelta(days=1),
            end_date=timezone.localdate() + dt.timedelta(days=1),
            audience=CalendarEvent.Audience.CLASS,
            class_obj=other_class,
            is_public=True,
            created_by=user,
            updated_by=user,
        )
        own_announcement = Announcement.objects.create(
            title="Comunicado do filho",
            body="Conteúdo permitido",
            audience=Announcement.Audience.CLASS,
            class_obj=own_activity.class_obj,
            author=user,
            sent_at=timezone.now(),
            created_by=user,
            updated_by=user,
        )
        older_announcement = Announcement.objects.create(
            title="Comunicado anterior do filho",
            body="Conteúdo permitido anterior",
            audience=Announcement.Audience.CLASS,
            class_obj=own_activity.class_obj,
            author=user,
            sent_at=timezone.now() - dt.timedelta(days=1),
            created_by=user,
            updated_by=user,
        )
        Announcement.objects.create(
            title="Comunicado externo",
            body="Conteúdo oculto",
            audience=Announcement.Audience.CLASS,
            class_obj=other_class,
            author=user,
            sent_at=timezone.now(),
            created_by=user,
            updated_by=user,
        )

        selector = DashboardSelector()

        assert selector.get_total_students(guardian_user) == 1
        assert selector.get_total_classes(guardian_user) == 1
        assert selector.get_today_attendance_rate(guardian_user) == {
            "rate": 100.0,
            "total": 1,
            "present": 1,
        }
        assert selector.get_students_at_risk_count(guardian_user) == 0
        assert [item["title"] for item in selector.get_pending_activities(user=guardian_user)] == [
            own_activity.title
        ]
        assert [item["id"] for item in selector.get_upcoming_events(user=guardian_user)] == [
            str(own_event.pk)
        ]
        assert [item["id"] for item in selector.get_recent_announcements(user=guardian_user)] == [
            str(own_announcement.pk),
            str(older_announcement.pk),
        ]

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
