"""DashboardSelector: KPIs agregados para o dashboard escolar e executivo."""

from __future__ import annotations

import datetime as dt
import logging

from django.db.models import Count

from base.selectors import BaseSelector

logger = logging.getLogger(__name__)


class DashboardSelector(BaseSelector):
    """Selector de indicadores para dashboards — escolar e executivo."""

    @property
    def model_class(self):
        from dashboard.models import DashboardWidget

        return DashboardWidget

    # ── KPIs escolares (por tenant) ──────────────────────────────────────────

    def get_total_students(self) -> int:
        """Total de alunos ativos na escola."""
        from students.models import Student

        return Student.objects.filter(is_active=True).count()

    def get_total_teachers(self) -> int:
        """Total de professores ativos na escola."""
        from teachers.models import Teacher

        return Teacher.objects.filter(is_active=True).count()

    def get_total_classes(self) -> int:
        """Total de turmas ativas na escola."""
        from classes.models import Class

        return Class.objects.filter(is_active=True).count()

    def get_total_guardians(self) -> int:
        """Total de responsaveis ativos na escola."""
        from guardians.models import Guardian

        return Guardian.objects.filter(is_active=True).count()

    def get_today_attendance_rate(self) -> dict | None:
        """Frequencia do dia atual: percentual de alunos presentes."""
        from attendance.models import AttendanceEntry

        today = dt.date.today()
        entries = AttendanceEntry.objects.filter(record__date=today)
        total = entries.count()
        if total == 0:
            return None
        presences = entries.filter(
            status__in=[AttendanceEntry.Status.PRESENT, AttendanceEntry.Status.JUSTIFIED]
        ).count()
        return {"rate": round((presences / total) * 100, 2), "total": total, "present": presences}

    def get_weekly_attendance(self) -> list[dict]:
        """Frequencia dos ultimos 7 dias: [{date, rate, total, present}, ...]."""
        from attendance.models import AttendanceEntry

        today = dt.date.today()
        result = []
        for i in range(6, -1, -1):
            day = today - dt.timedelta(days=i)
            entries = AttendanceEntry.objects.filter(record__date=day)
            total = entries.count()
            presences = (
                entries.filter(
                    status__in=[AttendanceEntry.Status.PRESENT, AttendanceEntry.Status.JUSTIFIED]
                ).count()
                if total > 0
                else 0
            )
            result.append(
                {
                    "date": day.isoformat(),
                    "label": day.strftime("%a %d/%m"),
                    "rate": round((presences / total) * 100, 2) if total > 0 else None,
                    "total": total,
                    "present": presences,
                }
            )
        return result

    def get_students_at_risk_count(self) -> int:
        """Total de alunos com frequencia abaixo de 75%."""
        from attendance.selectors import AttendanceSelector
        from classes.models import Class

        count = 0
        for cls in Class.objects.filter(is_active=True):
            at_risk = AttendanceSelector().get_students_at_risk(cls.pk)
            count += len(at_risk)
        return count

    def get_pending_activities(self, days: int = 3) -> list[dict]:
        """Atividades com entrega nos proximos N dias."""
        from activities.models import Activity

        today = dt.date.today()
        horizon = today + dt.timedelta(days=days)
        qs = (
            Activity.objects.filter(due_date__gte=today, due_date__lte=horizon, is_active=True)
            .select_related("subject", "class_obj", "teacher")
            .order_by("due_date")[:10]
        )
        return [
            {
                "id": str(a.pk),
                "title": a.title,
                "subject": a.subject.name,
                "class_obj": str(a.class_obj),
                "due_date": a.due_date.isoformat(),
            }
            for a in qs
        ]

    def get_upcoming_events(self, days: int = 7) -> list[dict]:
        """Proximos eventos do calendario."""
        from academic_calendar.selectors import CalendarSelector

        events = CalendarSelector().get_upcoming_events(days=days)[:5]
        return [
            {
                "id": str(e.pk),
                "title": e.title,
                "start_date": e.start_date.isoformat(),
                "type": e.get_type_display(),
            }
            for e in events
        ]

    def get_recent_announcements(self, limit: int = 5) -> list[dict]:
        """Ultimos comunicados enviados."""
        from notifications.models import Announcement

        qs = Announcement.objects.filter(sent_at__isnull=False).order_by("-sent_at")[:limit]
        return [
            {
                "id": str(a.pk),
                "title": a.title,
                "sent_at": a.sent_at.isoformat() if a.sent_at else None,
                "audience": a.get_audience_display(),
            }
            for a in qs
        ]

    # ── KPIs executivos (multi-tenant — schema public) ───────────────────────

    def get_total_tenants(self) -> int:
        """Numero de escolas ativas na plataforma."""
        from core.models import School

        return School.objects.filter(is_active=True).count()

    def get_platform_users(self) -> dict:
        """Total de usuarios por tipo em toda a plataforma."""

        from core.models import CustomUser

        # Nota: em schema public, CustomUser e compartilhado.
        # Dados por tenant requerem iteracao sobre schemas.
        total = CustomUser.objects.filter(is_active=True).count()
        teachers = CustomUser.objects.filter(teacher_profile__isnull=False).count()
        students = CustomUser.objects.filter(student_profile__isnull=False).count()
        guardians = CustomUser.objects.filter(guardian_profile__isnull=False).count()
        return {
            "total": total,
            "teachers": teachers,
            "students": students,
            "guardians": guardians,
        }

    def get_platform_growth(self, months: int = 6) -> list[dict]:
        """Crescimento de tenants nos ultimos N meses."""
        from django.db.models.functions import TruncMonth

        from core.models import School

        since = dt.date.today().replace(day=1) - dt.timedelta(days=30 * months)
        qs = (
            School.objects.filter(created_at__gte=since)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        return [{"month": item["month"].strftime("%Y-%m"), "count": item["count"]} for item in qs]
