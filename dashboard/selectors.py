"""DashboardSelector: KPIs agregados para o dashboard escolar e executivo."""

from __future__ import annotations

import datetime as dt

from django.db.models import Count, F, OuterRef, Q, Subquery
from django.utils import timezone

from base.selectors import BaseSelector


class DashboardSelector(BaseSelector):
    """Selector de indicadores para dashboards — escolar e executivo."""

    @property
    def model_class(self):
        from dashboard.models import DashboardWidget

        return DashboardWidget

    # ── KPIs escolares (por tenant) ──────────────────────────────────────────

    @staticmethod
    def _guardian_student_ids(user):
        """Retorna o escopo canônico quando o usuário é responsável."""
        from core.permissions import role_name

        if role_name(user) != "GUARDIAN":
            return None
        from guardians.selectors import GuardianSelector

        return GuardianSelector().custodial_student_ids_for_user(user.pk)

    @classmethod
    def _guardian_active_class_ids(cls, user):
        """Retorna turmas com matrícula ativa dos alunos sob guarda."""
        student_ids = cls._guardian_student_ids(user)
        if student_ids is None:
            return None
        from classes.contracts import Enrollment

        return (
            Enrollment.objects.filter(
                student_id__in=student_ids,
                status=Enrollment.Status.ACTIVE,
                is_active=True,
                deleted_at__isnull=True,
                class_obj__is_active=True,
                class_obj__deleted_at__isnull=True,
            )
            .values_list("class_obj_id", flat=True)
            .distinct()
        )

    def get_total_students(self, user=None) -> int:
        """Total de alunos ativos na escola."""
        from students.contracts import Student

        queryset = Student.objects.filter(is_active=True)
        student_ids = self._guardian_student_ids(user)
        if student_ids is not None:
            queryset = queryset.filter(pk__in=student_ids)
        return queryset.count()

    def get_total_teachers(self) -> int:
        """Total de professores ativos na escola."""
        from teachers.contracts import Teacher

        return Teacher.objects.filter(is_active=True).count()

    def get_total_classes(self, user=None) -> int:
        """Total de turmas ativas na escola."""
        from classes.contracts import Class

        queryset = Class.objects.filter(is_active=True)
        class_ids = self._guardian_active_class_ids(user)
        if class_ids is not None:
            queryset = queryset.filter(pk__in=class_ids)
        return queryset.distinct().count()

    def get_total_guardians(self) -> int:
        """Total de responsaveis ativos na escola."""
        from guardians.contracts import Guardian

        return Guardian.objects.filter(is_active=True).count()

    def get_today_attendance_rate(self, user=None) -> dict | None:
        """Frequencia do dia atual: percentual de alunos presentes."""
        from attendance.contracts import AttendanceEntry

        today = timezone.localdate()
        entries = AttendanceEntry.objects.filter(record__date=today)
        student_ids = self._guardian_student_ids(user)
        if student_ids is not None:
            entries = entries.filter(student_id__in=student_ids)
        total = entries.count()
        if total == 0:
            return None
        presences = entries.filter(
            status__in=[AttendanceEntry.Status.PRESENT, AttendanceEntry.Status.JUSTIFIED]
        ).count()
        return {"rate": round((presences / total) * 100, 2), "total": total, "present": presences}

    def get_weekly_attendance(self, user=None) -> list[dict]:
        """Frequencia dos ultimos 7 dias: [{date, rate, total, present}, ...]."""
        from attendance.contracts import AttendanceEntry

        today = timezone.localdate()
        student_ids = self._guardian_student_ids(user)
        result = []
        for i in range(6, -1, -1):
            day = today - dt.timedelta(days=i)
            entries = AttendanceEntry.objects.filter(record__date=day)
            if student_ids is not None:
                entries = entries.filter(student_id__in=student_ids)
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

    def get_students_at_risk_count(self, user=None) -> int:
        """Total de alunos com frequencia abaixo de 75%."""
        from attendance.selectors import AttendanceSelector
        from classes.contracts import Class

        student_ids = self._guardian_student_ids(user)
        class_ids = (
            self._guardian_active_class_ids(user)
            if student_ids is not None
            else Class.objects.filter(is_active=True).values("pk")
        )
        groups = AttendanceSelector().get_classes_attendance_summary(
            class_ids, student_ids=student_ids
        )
        if student_ids is not None:
            return len(
                {item["student"].pk for group in groups.values() for item in group["at_risk"]}
            )
        return sum(len(group["at_risk"]) for group in groups.values())

    def get_financial_kpis(self, user=None) -> dict:
        """KPIs financeiros operacionais para o dashboard escolar."""
        from financeiro.selectors import BillingSelector

        return BillingSelector(user=user).finance_kpis()

    def get_pending_activities(self, days: int = 3, *, user=None) -> list[dict]:
        """Atividades com entrega nos proximos N dias."""
        from activities.contracts import Activity

        today = timezone.localdate()
        horizon = today + dt.timedelta(days=days)
        qs = Activity.objects.filter(
            due_date__gte=today, due_date__lte=horizon, is_active=True
        ).select_related("subject", "class_obj", "teacher")
        class_ids = self._guardian_active_class_ids(user)
        if class_ids is not None:
            qs = qs.filter(class_obj_id__in=class_ids)
        qs = qs.distinct().order_by("due_date")[:10]
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

    def get_upcoming_events(self, days: int = 7, *, user=None) -> list[dict]:
        """Proximos eventos do calendario."""
        from academic_calendar.selectors import CalendarSelector

        events = CalendarSelector().get_upcoming_events(days=days, user=user)[:5]
        return [
            {
                "id": str(e.pk),
                "title": e.title,
                "start_date": e.start_date.isoformat(),
                "type": e.get_type_display(),
            }
            for e in events
        ]

    def get_recent_announcements(self, limit=5, *, user=None):
        """Publicações autorizadas; não reutiliza audiência global do cache escolar."""
        if user is None:
            return []
        from notifications.announcement_selectors import AnnouncementSelector

        return [
            {
                "id": str(item.announcement_id),
                "title": item.title,
                "sent_at": item.published_at.isoformat(),
                "audience": item.get_audience_display(),
            }
            for item in AnnouncementSelector()
            .visible_revisions(user)
            .order_by("-published_at")[:limit]
        ]

    def get_diary_kpis(self, user) -> dict:
        """Retorna indicadores operacionais da agenda conforme o papel atual."""
        from core.permissions import role_name
        from student_diary.contracts import DiaryPublication, DiarySheet, DiaryViewReceipt

        role = role_name(user)
        if role == "GUARDIAN":
            from guardians.selectors import GuardianSelector

            receipts = DiaryViewReceipt.objects.filter(
                guardian__user=user,
                guardian__is_active=True,
                guardian__deleted_at__isnull=True,
                entry__student_id__in=GuardianSelector().custodial_student_ids_for_user(user.pk),
            ).distinct()
            return {
                "role": role,
                "unread": receipts.filter(first_viewed_at__isnull=True).count(),
                "published": receipts.count(),
            }
        sheets = DiarySheet.objects.all()
        if role == "TEACHER":
            from core.access_selectors import ObjectAccessSelector

            sheets = sheets.filter(
                class_obj_id__in=ObjectAccessSelector.teacher_classes(user.pk).values("pk")
            )
        latest_publication = (
            DiaryPublication.objects.filter(sheet_id=OuterRef("entry__publication__sheet_id"))
            .order_by("-revision_number")
            .values("pk")[:1]
        )
        receipts = (
            DiaryViewReceipt.objects.filter(entry__publication__sheet__in=sheets)
            .annotate(latest_publication_id=Subquery(latest_publication))
            .filter(entry__publication_id=F("latest_publication_id"))
        )
        notified = receipts.count()
        viewed_24h = receipts.filter(
            first_viewed_at__isnull=False,
            first_viewed_at__lte=F("entry__publication__published_at") + dt.timedelta(hours=24),
        ).count()
        durations = (
            DiaryPublication.objects.filter(
                sheet__in=sheets,
                sheet__submitted_at__isnull=False,
            )
            .annotate(duration=F("published_at") - F("sheet__submitted_at"))
            .order_by("duration", "pk")
            .values_list("duration", flat=True)
        )
        count = durations.count()
        centers = list(durations[(count - 1) // 2 : count // 2 + 1]) if count else []
        median_hours = (
            round(sum(value.total_seconds() for value in centers) / len(centers) / 3600, 1)
            if centers
            else None
        )
        completion = self._diary_publication_completion(sheets)
        return {
            "role": role,
            "draft": sheets.filter(status=DiarySheet.Status.DRAFT).count(),
            "pending_review": sheets.filter(status=DiarySheet.Status.PENDING_REVIEW).count(),
            "changes_requested": sheets.filter(status=DiarySheet.Status.CHANGES_REQUESTED).count(),
            "view_rate_24h": round(viewed_24h * 100 / notified, 1) if notified else None,
            "approval_median_hours": median_hours,
            **completion,
        }

    @staticmethod
    def _diary_publication_completion(sheets) -> dict:
        """Calcula conclusão dos últimos 28 dias usando o calendário escolar."""
        from academic_calendar.contracts import CalendarEvent, Holiday
        from classes.contracts import Class

        end = timezone.localdate()
        start = end - dt.timedelta(days=27)
        holidays = Holiday.objects.filter(Q(date__range=(start, end)) | Q(is_recurring=True))
        blocked = set()
        for holiday in holidays:
            years = {start.year, end.year} if holiday.is_recurring else {holiday.date.year}
            for year in years:
                try:
                    current = holiday.date.replace(year=year)
                except ValueError:
                    continue
                if start <= current <= end:
                    blocked.add(current)
        events = CalendarEvent.objects.filter(
            type__in=[CalendarEvent.Type.HOLIDAY, CalendarEvent.Type.NON_SCHOOL_DAY],
            is_cancelled=False,
            start_date__lte=end,
            end_date__gte=start,
        )
        for event in events:
            current = max(start, event.start_date)
            while current <= min(end, event.end_date):
                blocked.add(current)
                current += dt.timedelta(days=1)
        working_days = sum(
            1
            for offset in range(28)
            if (start + dt.timedelta(days=offset)).weekday() < 5
            and start + dt.timedelta(days=offset) not in blocked
        )
        class_count = Class.objects.filter(
            education_stage=Class.EducationStage.EARLY_CHILDHOOD
        ).count()
        expected = class_count * working_days
        published = (
            sheets.filter(date__range=(start, end), publications__isnull=False).distinct().count()
        )
        return {
            "publication_completion_rate": (
                round(published * 100 / expected, 1) if expected else None
            ),
            "published_class_days": published,
            "expected_class_days": expected,
        }

    # ── KPIs executivos (multi-tenant — schema public) ───────────────────────

    def get_total_tenants(self) -> int:
        """Numero de escolas ativas na plataforma."""
        from tenancy.contracts import School

        return School.objects.filter(is_active=True).count()

    def get_platform_users(self) -> dict:
        """Total de usuarios por tipo em toda a plataforma."""

        from core.contracts import CustomUser

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

        from tenancy.contracts import School

        since = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        since -= dt.timedelta(days=30 * months)
        qs = (
            School.objects.filter(created_at__gte=since)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        return [{"month": item["month"].strftime("%Y-%m"), "count": item["count"]} for item in qs]
