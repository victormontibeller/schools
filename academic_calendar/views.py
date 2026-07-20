"""Views HTMX para o calendario academico."""

import datetime as dt
import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from academic_calendar.forms import AcademicYearForm, EventForm, HolidayForm
from academic_calendar.selectors import AcademicYearSelector, CalendarSelector, HolidaySelector
from academic_calendar.services import CalendarService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_querystring, build_sorting, resolve_listing_state
from core.permissions import CREATE, EDIT, VIEW, access_policy

logger = logging.getLogger(__name__)
EVENT_SORTS = {
    "title": "title",
    "-title": "-title",
    "start_date": "start_date",
    "-start_date": "-start_date",
    "type": "type",
    "-type": "-type",
}
HOLIDAY_SORTS = {
    "name": "name",
    "-name": "-name",
    "date": "date",
    "-date": "-date",
    "type": "type",
    "-type": "-type",
}
ACADEMIC_YEAR_SORTS = {
    "name": "name",
    "-name": "-name",
    "start_date": "start_date",
    "-start_date": "-start_date",
    "status": "status",
    "-status": "-status",
}


@login_required
def calendar_month(request, year: int | None = None, month: int | None = None):
    """Exibe o calendário mensal navegável por HTMX."""
    today = dt.date.today()
    year = int(year) if year else today.year
    month = int(month) if month else today.month
    selected_date = _resolve_selected_date(request.GET.get("selected_date"), year, month, today)
    ctx = CalendarSelector().get_month_grid(year, month)
    ctx.update(
        {
            "selected_date": selected_date,
            "day_agenda": CalendarSelector().get_day_agenda(selected_date),
        }
    )
    if request.headers.get("HX-Request"):
        if request.GET.get("component") == "agenda":
            return _render_day_agenda(request, selected_date)
        return render(request, "academic_calendar/partials/calendar_workspace_content.html", ctx)
    return render(request, "academic_calendar/calendar_month.html", ctx)


@login_required
def events_list(request):
    """Lista os próximos eventos e oferece atalho para criar."""
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request, scope="events_list", allowed_sorts=set(EVENT_SORTS), default_sort="start_date"
    )
    context = _listing_context(
        request,
        result=CalendarSelector().list_upcoming_events(
            state["q"], EVENT_SORTS[state["sort"]], page
        ),
        q=state["q"],
        sort=state["sort"],
        sortable_fields=["title", "start_date", "type"],
        breadcrumbs=[{"label": "Home", "url": "dashboard"}, {"label": "Eventos", "url": None}],
    )
    if request.headers.get("HX-Request"):
        return render(request, "academic_calendar/partials/events_table.html", context)
    return render(request, "academic_calendar/events_list.html", context)


@login_required
def event_create(request):
    """Exibe/Processa o formulário de criação de evento."""
    initial = {}
    if request.GET.get("date"):
        try:
            selected_date = dt.date.fromisoformat(request.GET["date"])
            initial = {"start_date": selected_date, "end_date": selected_date}
        except ValueError:
            initial = {}
    form = EventForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            event = CalendarService(user=request.user).create_event(_event_data(form.cleaned_data))
            if request.headers.get("HX-Request"):
                return _render_day_agenda(request, event.start_date)
            return redirect(_calendar_url(event.start_date))
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
        except ObjectNotFoundError as exc:
            logger.warning(
                "Entidade nao encontrada ao criar evento",
                extra={"exception_type": type(exc).__name__},
            )
            from django.contrib import messages

            messages.error(request, str(exc))
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academic_calendar/partials/event_information_form.html",
            {"form": form, "selected_date": initial.get("start_date") or dt.date.today()},
        )
    return redirect(_calendar_url(initial.get("start_date") or dt.date.today()))


@login_required
def event_detail(request, pk):
    """Retorna ficha no card da agenda ou preserva rota legada por redirecionamento."""
    event = CalendarSelector().get_by_id(pk)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academic_calendar/partials/event_information_card.html",
            {
                "event": event,
                "selected_date": _selected_date_from_request(request, event.start_date),
            },
        )
    return redirect(_calendar_url(event.start_date))


@login_required
def event_edit(request, pk):
    """Edita evento substituindo apenas o card lateral da agenda."""
    event = CalendarSelector().get_by_id(pk)
    selected_date = _selected_date_from_request(request, event.start_date)
    form = EventForm(request.POST or None, instance=event)
    if request.method == "POST" and form.is_valid():
        try:
            event = CalendarService(user=request.user).update_event(
                pk, _event_data(form.cleaned_data)
            )
            if request.headers.get("HX-Request"):
                return _render_day_agenda(request, selected_date)
            return redirect(_calendar_url(event.start_date))
        except ValidationError as exc:
            apply_validation_errors(form, exc)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "academic_calendar/partials/event_information_form.html",
            {"form": form, "event": event, "selected_date": selected_date},
        )
    return redirect(_calendar_url(event.start_date))


@login_required
def event_cancel(request, pk):
    """Cancela um evento via POST (HTMX)."""
    if request.method != "POST":
        return redirect("event_detail", pk=pk)
    try:
        CalendarService(user=request.user).cancel_event(pk, request.POST.get("reason", ""))
    except (ValidationError, ObjectNotFoundError, BusinessRuleViolationError) as exc:
        logger.warning(
            "Erro ao cancelar evento",
            extra={"event_id": str(pk), "exception_type": type(exc).__name__},
        )
        from django.contrib import messages

        messages.error(request, str(exc))
    return redirect("event_detail", pk=pk)


@login_required
@access_policy("holidays", VIEW)
def holidays_list(request):
    """Lista feriados seguindo o padrão de listagem compartilhada."""
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request, scope="holidays_list", allowed_sorts=set(HOLIDAY_SORTS), default_sort="date"
    )
    context = _listing_context(
        request,
        result=HolidaySelector().list_holidays(
            dt.date.today().year, state["q"], HOLIDAY_SORTS[state["sort"]], page
        ),
        q=state["q"],
        sort=state["sort"],
        sortable_fields=["name", "date", "type"],
        breadcrumbs=[
            {"label": "Home", "url": "dashboard"},
            {"label": "Feriados", "url": None},
        ],
    )
    if request.headers.get("HX-Request"):
        return render(request, "academic_calendar/partials/holidays_table.html", context)
    return render(request, "academic_calendar/holidays_list.html", context)


@login_required
@access_policy("holidays", CREATE)
def holiday_create(request):
    """Cria um feriado no formulário compacto."""
    form = HolidayForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            CalendarService(user=request.user).create_holiday(form.cleaned_data)
            return redirect("holidays_list")
        except ValidationError as exc:
            apply_validation_errors(form, exc)
    return render(
        request, "academic_calendar/holiday_form.html", {"form": form, "title": "Novo Feriado"}
    )


@login_required
@access_policy("holidays", EDIT)
def holiday_edit(request, pk):
    """Edita um feriado pela primeira coluna da listagem."""
    holiday = HolidaySelector().get_by_id(pk)
    form = HolidayForm(request.POST or None, instance=holiday)
    if request.method == "POST" and form.is_valid():
        CalendarService(user=request.user).update_holiday(pk, form.cleaned_data)
        return redirect("holidays_list")
    return render(
        request, "academic_calendar/holiday_form.html", {"form": form, "title": "Editar Feriado"}
    )


@login_required
@access_policy("academic_years", VIEW)
def academic_years_list(request):
    """Lista anos letivos seguindo o padrão de listagem compartilhada."""
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="academic_years_list",
        allowed_sorts=set(ACADEMIC_YEAR_SORTS),
        default_sort="-start_date",
    )
    context = _listing_context(
        request,
        result=AcademicYearSelector().list_academic_years(
            state["q"], ACADEMIC_YEAR_SORTS[state["sort"]], page
        ),
        q=state["q"],
        sort=state["sort"],
        sortable_fields=["name", "start_date", "status"],
        breadcrumbs=[
            {"label": "Home", "url": "dashboard"},
            {"label": "Anos Letivos", "url": None},
        ],
    )
    if request.headers.get("HX-Request"):
        return render(request, "academic_calendar/partials/academic_years_table.html", context)
    return render(request, "academic_calendar/academic_years_list.html", context)


@login_required
@access_policy("academic_years", CREATE)
def academic_year_create(request):
    """Cria um ano letivo no formulário compacto."""
    form = AcademicYearForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            CalendarService(user=request.user).create_academic_year(form.cleaned_data)
            return redirect("academic_years_list")
        except ValidationError as exc:
            apply_validation_errors(form, exc)
    return render(
        request,
        "academic_calendar/academic_year_form.html",
        {"form": form, "title": "Novo Ano Letivo"},
    )


@login_required
@access_policy("academic_years", EDIT)
def academic_year_edit(request, pk):
    """Edita um ano letivo pela primeira coluna da listagem."""
    academic_year = AcademicYearSelector().get_by_id(pk)
    form = AcademicYearForm(request.POST or None, instance=academic_year)
    if request.method == "POST" and form.is_valid():
        CalendarService(user=request.user).update_academic_year(pk, form.cleaned_data)
        return redirect("academic_years_list")
    return render(
        request,
        "academic_calendar/academic_year_form.html",
        {"form": form, "title": "Editar Ano Letivo"},
    )


def _listing_context(request, *, result, q, sort, sortable_fields, breadcrumbs):
    """Monta o contexto comum às listagens do calendário."""
    return {
        "result": result,
        "q": q,
        "sort": sort,
        "sorting": build_sorting(current_sort=sort, search=q, sortable_fields=sortable_fields),
        "list_query": build_querystring({"q": q, "sort": sort}),
        "breadcrumb_items": breadcrumbs,
    }


def _resolve_selected_date(value: str | None, year: int, month: int, today: dt.date) -> dt.date:
    """Preserva a data selecionada no mês ou aplica o fallback padrão."""
    if value:
        try:
            selected = dt.date.fromisoformat(value)
            if selected.year == year and selected.month == month:
                return selected
        except ValueError:
            pass
    return today if today.year == year and today.month == month else dt.date(year, month, 1)


def _event_data(data: dict) -> dict:
    """Converte relações do ModelForm no contrato do service."""
    result = data.copy()
    result["class_obj_id"] = result.pop("class_obj", None).pk if result.get("class_obj") else None
    result["academic_year_id"] = (
        result.pop("academic_year", None).pk if result.get("academic_year") else None
    )
    return result


def _calendar_url(selected_date: dt.date) -> str:
    from django.urls import reverse

    url = reverse(
        "calendar_month_specific",
        kwargs={"year": selected_date.year, "month": selected_date.month},
    )
    return f"{url}?selected_date={selected_date.isoformat()}"


def _selected_date_from_request(request, fallback: dt.date) -> dt.date:
    try:
        return dt.date.fromisoformat(request.GET.get("selected_date", fallback.isoformat()))
    except ValueError:
        return fallback


def _render_day_agenda(request, selected_date: dt.date):
    return render(
        request,
        "academic_calendar/partials/day_agenda.html",
        {
            "selected_date": selected_date,
            "day_agenda": CalendarSelector().get_day_agenda(selected_date),
        },
    )
