"""CalendarSelector: consultas somente-leitura do calendário acadêmico."""

import datetime as dt

from django.db.models import Q

from base.selectors import BaseSelector


class CalendarSelector(BaseSelector):
    """Selector para a entidade CalendarEvent — calendário mensal e por intervalo."""

    @property
    def model_class(self):
        from academic_calendar.models import CalendarEvent

        return CalendarEvent

    def get_events_by_month(self, year: int, month: int):
        """Retorna eventos ativos (não cancelados) que tocam o mês dado.

        Um evento que inicia antes do mês e termina dentro dele é incluído.
        """
        from academic_calendar.models import CalendarEvent

        first = dt.date(year, month, 1)
        if month == 12:
            last = dt.date(year, month, 31)
        else:
            last = dt.date(year, month + 1, 1) - dt.timedelta(days=1)

        return (
            CalendarEvent.objects.filter(
                is_cancelled=False, start_date__lte=last, end_date__gte=first
            )
            .select_related("class_obj", "academic_year")
            .order_by("start_date", "start_time")
        )

    def get_events_by_range(
        self, start_date: dt.date, end_date: dt.date, audience: str | None = None
    ):
        """Retorna eventos ativos num intervalo, opcionalmente filtrados por público."""
        from academic_calendar.models import CalendarEvent

        qs = CalendarEvent.objects.filter(
            is_cancelled=False, start_date__lte=end_date, end_date__gte=start_date
        )
        if audience:
            qs = qs.filter(audience=audience)
        return qs.select_related("class_obj").order_by("start_date", "start_time")

    def get_upcoming_events(self, days: int = 7):
        """Retorna eventos ativos a partir de hoje até `days` à frente."""
        from academic_calendar.models import CalendarEvent

        today = dt.date.today()
        horizon = today + dt.timedelta(days=days)
        return (
            CalendarEvent.objects.filter(
                is_cancelled=False, start_date__gte=today, start_date__lte=horizon
            )
            .select_related("class_obj")
            .order_by("start_date", "start_time")
        )

    def get_month_grid(self, year: int, month: int):
        """Retorna grade mensal 6x7 com eventos indexados por dia.

        Returns:
            dict com weeks, by_day, prev_year, prev_month, next_year, next_month,
            month_name, today.
        """
        import calendar as cal

        today = dt.date.today()
        events = self.get_events_by_month(year, month)

        # Indexa eventos por dia.
        by_day: dict[dt.date, list] = {}
        for ev in events:
            current = ev.start_date
            while current <= ev.end_date:
                by_day.setdefault(current, []).append(ev)
                current += dt.timedelta(days=1)

        # Constrói grade 6x7.
        first = dt.date(year, month, 1)
        offset = first.weekday() + 1 if first.weekday() < 6 else 0
        grid_start = first - dt.timedelta(days=offset)
        weeks: list[list[dt.date]] = []
        cur = grid_start
        for _ in range(6):
            weeks.append([cur + dt.timedelta(days=i) for i in range(7)])
            cur += dt.timedelta(days=7)

        prev_d = dt.date(year, month, 1) - dt.timedelta(days=1)
        next_d = dt.date(year, month, 1) + dt.timedelta(days=31)

        return {
            "year": year,
            "month": month,
            "month_name": cal.month_name[month],
            "weeks": weeks,
            "by_day": by_day,
            "today": today,
            "prev_year": prev_d.year,
            "prev_month": prev_d.month,
            "next_year": next_d.year,
            "next_month": next_d.month,
        }

    def get_academic_year_events(self, academic_year_id):
        """Retorna os eventos vinculados a um ano letivo."""
        from academic_calendar.models import CalendarEvent

        return (
            CalendarEvent.objects.filter(academic_year_id=academic_year_id, is_cancelled=False)
            .select_related("class_obj")
            .order_by("start_date", "start_time")
        )


class HolidaySelector(BaseSelector):
    """Selector para feriados."""

    @property
    def model_class(self):
        from academic_calendar.models import Holiday

        return Holiday

    def list_holidays(self, year: int | None = None):
        """Lista feriados; se `year` informado, inclui os recorrentes ajustados ao ano."""
        from academic_calendar.models import Holiday

        qs = Holiday.objects.all()
        if year is not None:
            qs = qs.filter(Q(date__year=year) | Q(is_recurring=True))
        return qs.order_by("date")


class AcademicYearSelector(BaseSelector):
    """Selector para anos letivos."""

    @property
    def model_class(self):
        from academic_calendar.models import AcademicYear

        return AcademicYear

    def list_academic_years(self):
        """Lista anos letivos ordenados por início (mais recente primeiro)."""
        from academic_calendar.models import AcademicYear

        return AcademicYear.objects.all().order_by("-start_date")
