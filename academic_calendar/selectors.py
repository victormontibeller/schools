"""CalendarSelector: consultas somente-leitura do calendário acadêmico."""

import datetime as dt

from django.db.models import Q

from base.selectors import MAX_PAGE_SIZE, BaseSelector, PageResult


def _page(queryset, page: int, page_size: int) -> PageResult:
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)
    page = max(1, page)
    total = queryset.count()
    offset = (page - 1) * page_size
    return PageResult(
        items=list(queryset[offset : offset + page_size]),
        total=total,
        page=page,
        page_size=page_size,
    )


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

    def list_upcoming_events(self, search="", order_by="start_date", page=1, page_size=20):
        """Lista os próximos eventos com busca, ordenação e paginação."""
        queryset = self.get_upcoming_events(days=30)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(class_obj__name__icontains=search)
            )
        return _page(queryset.order_by(order_by, "start_time"), page, page_size)

    def get_month_grid(self, year: int, month: int):
        """Retorna grade mensal 6x7 com eventos e feriados indexados por dia.

        Returns:
            dict com weeks, by_day, prev_year, prev_month, next_year, next_month,
            month_name, today.
        """
        import calendar as cal

        today = dt.date.today()
        from academic_calendar.models import Holiday

        events = self.get_events_by_month(year, month)
        first = dt.date(year, month, 1)
        if month == 12:
            last = dt.date(year, month, 31)
        else:
            last = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
        holidays = Holiday.objects.filter(
            Q(date__gte=first, date__lte=last) | Q(is_recurring=True, date__month=month)
        ).order_by("date", "name")

        # Indexa eventos por dia e adapta feriados ao contrato de prévia do template.
        by_day: dict[dt.date, list] = {}
        for ev in events:
            current = ev.start_date
            while current <= ev.end_date:
                by_day.setdefault(current, []).append(ev)
                current += dt.timedelta(days=1)
        for holiday in holidays:
            holiday_date = dt.date(year, month, holiday.date.day)
            by_day.setdefault(holiday_date, []).append({"title": holiday.name, "type": "holiday"})

        # Constrói grade 6x7.
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

    def get_day_agenda(self, selected_date: dt.date) -> list[dict]:
        """Compõe eventos, feriados e dias não letivos da data selecionada."""
        from academic_calendar.models import Holiday

        events = self.get_events_by_range(selected_date, selected_date)
        items = [
            {
                "kind": "event",
                "item": event,
                "time": event.start_time,
                "all_day": event.start_time is None,
            }
            for event in events
        ]
        holidays = Holiday.objects.filter(
            Q(date=selected_date)
            | Q(is_recurring=True, date__month=selected_date.month, date__day=selected_date.day)
        ).order_by("name")
        items.extend(
            {"kind": "holiday", "item": holiday, "time": None, "all_day": True}
            for holiday in holidays
        )
        return sorted(items, key=lambda entry: (not entry["all_day"], entry["time"] or dt.time.min))

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

    def list_holidays(
        self, year: int | None = None, search="", order_by="date", page=1, page_size=20
    ):
        """Lista feriados com busca, ordenação e paginação."""
        from academic_calendar.models import Holiday

        qs = Holiday.objects.all()
        if year is not None:
            qs = qs.filter(Q(date__year=year) | Q(is_recurring=True))
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(type__icontains=search))
        return _page(qs.order_by(order_by), page, page_size)


class AcademicYearSelector(BaseSelector):
    """Selector para anos letivos."""

    @property
    def model_class(self):
        from academic_calendar.models import AcademicYear

        return AcademicYear

    def list_academic_years(self, search="", order_by="-start_date", page=1, page_size=20):
        """Lista anos letivos com busca, ordenação e paginação."""
        from academic_calendar.models import AcademicYear

        queryset = AcademicYear.objects.all()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(status__icontains=search))
        return _page(queryset.order_by(order_by), page, page_size)
