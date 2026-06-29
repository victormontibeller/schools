"""Views HTMX para o calendário acadêmico."""

import calendar as cal
import datetime as dt

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from academic_calendar.forms import AcademicYearForm, EventForm, HolidayForm
from academic_calendar.selectors import AcademicYearSelector, CalendarSelector, HolidaySelector
from academic_calendar.services import CalendarService
from base.exceptions import ValidationError


def _month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    """Retorna o primeiro e o último dia do mês, considerando a grade visual."""
    first = dt.date(year, month, 1)
    # A grade começa no domingo anterior ao primeiro do mês.
    start = first - dt.timedelta(days=first.weekday() + 1 if first.weekday() < 6 else 0)
    # cal.monthrange devolve (weekday do dia 1, último dia)
    last_day = cal.monthrange(year, month)[1]
    last = dt.date(year, month, last_day)
    # A grade termina no sábado seguinte.
    end = last + dt.timedelta(days=5 - last.weekday())
    return start, end


@login_required
def calendar_month(request, year: int | None = None, month: int | None = None):
    """Exibe o calendário mensal navegável por HTMX."""
    today = dt.date.today()
    year = int(year) if year else today.year
    month = int(month) if month else today.month

    prev_d = dt.date(year, month, 1) - dt.timedelta(days=1)
    next_d = dt.date(year, month, 1) + dt.timedelta(days=31)
    events = CalendarSelector().get_events_by_month(year, month)

    # Indexa por dia para renderizar fácil na grade.
    by_day: dict[dt.date, list] = {}
    for ev in events:
        current = ev.start_date
        while current <= ev.end_date:
            by_day.setdefault(current, []).append(ev)
            current += dt.timedelta(days=1)

    # Constrói a grade 6x7 (semanas).
    first = dt.date(year, month, 1)
    grid_start = first - dt.timedelta(days=first.weekday() + 1 if first.weekday() < 6 else 0)
    weeks: list[list[dt.date]] = []
    cur = grid_start
    for _ in range(6):
        week = [cur + dt.timedelta(days=i) for i in range(7)]
        weeks.append(week)
        cur += dt.timedelta(days=7)

    ctx = {
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
    if request.headers.get("HX-Request"):
        return render(request, "academic_calendar/partials/calendar_grid.html", ctx)
    return render(request, "academic_calendar/calendar_month.html", ctx)


@login_required
def events_list(request):
    """Lista os próximos eventos e oferece atalho para criar."""
    events = CalendarSelector().get_upcoming_events(days=30)
    return render(request, "academic_calendar/events_list.html", {"events": events})


@login_required
def event_create(request):
    """Exibe/Processa o formulário de criação de evento."""
    form = EventForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            CalendarService(user=request.user).create_event(form.cleaned_data)
            return redirect("calendar_month")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    return render(
        request,
        "academic_calendar/event_form.html",
        {"form": form, "title": "Novo Evento"},
    )


@login_required
def event_detail(request, pk):
    """Exibe detalhes de um evento e permite cancelá-lo."""
    from academic_calendar.models import CalendarEvent

    event = get_object_or_404(CalendarEvent, pk=pk)
    return render(request, "academic_calendar/event_detail.html", {"event": event})


@login_required
def event_cancel(request, pk):
    """Cancela um evento via POST (HTMX)."""
    if request.method != "POST":
        return redirect("event_detail", pk=pk)
    try:
        CalendarService(user=request.user).cancel_event(pk, request.POST.get("reason", ""))
    except Exception as exc:
        from django.contrib import messages

        messages.error(request, str(exc))
    return redirect("event_detail", pk=pk)


@login_required
def holidays_list(request):
    """Lista feriados e o formulário de criação."""
    holidays = HolidaySelector().list_holidays(year=dt.date.today().year)
    form = HolidayForm()
    return render(
        request,
        "academic_calendar/holidays_list.html",
        {"holidays": holidays, "form": form, "title": "Feriados"},
    )


@login_required
def holiday_create(request):
    """Cria um feriado; redireciona de volta à lista."""
    if request.method != "POST":
        return redirect("holidays_list")
    form = HolidayForm(request.POST)
    if form.is_valid():
        try:
            CalendarService(user=request.user).create_holiday(form.cleaned_data)
        except ValidationError as exc:
            holidays = HolidaySelector().list_holidays(year=dt.date.today().year)
            return render(
                request,
                "academic_calendar/holidays_list.html",
                {"holidays": holidays, "form": form, "title": "Feriados", "errors": exc.errors},
            )
    return redirect("holidays_list")


@login_required
def academic_years_list(request):
    """Lista anos letivos e o formulário de criação."""
    years = AcademicYearSelector().list_academic_years()
    form = AcademicYearForm()
    return render(
        request,
        "academic_calendar/academic_years_list.html",
        {"years": years, "form": form, "title": "Anos Letivos"},
    )


@login_required
def academic_year_create(request):
    """Cria um ano letivo; redireciona de volta à lista."""
    if request.method != "POST":
        return redirect("academic_years_list")
    form = AcademicYearForm(request.POST)
    if form.is_valid():
        try:
            CalendarService(user=request.user).create_academic_year(form.cleaned_data)
        except ValidationError as exc:
            years = AcademicYearSelector().list_academic_years()
            return render(
                request,
                "academic_calendar/academic_years_list.html",
                {"years": years, "form": form, "title": "Anos Letivos", "errors": exc.errors},
            )
    return redirect("academic_years_list")
