"""Views HTMX para o calendario academico."""

import datetime as dt
import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from academic_calendar.forms import AcademicYearForm, EventForm, HolidayForm
from academic_calendar.selectors import AcademicYearSelector, CalendarSelector, HolidaySelector
from academic_calendar.services import CalendarService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError

logger = logging.getLogger(__name__)


@login_required
def calendar_month(request, year: int | None = None, month: int | None = None):
    """Exibe o calendário mensal navegável por HTMX."""
    today = dt.date.today()
    year = int(year) if year else today.year
    month = int(month) if month else today.month

    ctx = CalendarSelector().get_month_grid(year, month)
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
        except ObjectNotFoundError as exc:
            logger.warning("Entidade nao encontrada ao criar evento: %s", exc)
            from django.contrib import messages

            messages.error(request, str(exc))
    return render(
        request,
        "academic_calendar/event_form.html",
        {"form": form, "title": "Novo Evento"},
    )


@login_required
def event_detail(request, pk):
    """Exibe detalhes de um evento e permite cancelá-lo."""
    event = CalendarSelector().get_by_id(pk)
    return render(request, "academic_calendar/event_detail.html", {"event": event})


@login_required
def event_cancel(request, pk):
    """Cancela um evento via POST (HTMX)."""
    if request.method != "POST":
        return redirect("event_detail", pk=pk)
    try:
        CalendarService(user=request.user).cancel_event(pk, request.POST.get("reason", ""))
    except (ValidationError, ObjectNotFoundError, BusinessRuleViolationError) as exc:
        logger.warning("Erro ao cancelar evento: %s", exc, extra={"event_id": str(pk)})
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
