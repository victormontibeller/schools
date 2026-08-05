"""Composição compartilhada da matriz semanal e de suas URLs canônicas."""

from datetime import date, timedelta

from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from agenda.selectors import ScheduleSelector
from core.permissions import role_name


def as_of_from_request(request: HttpRequest) -> date:
    """Converte a referência da URL na segunda-feira canônica da sua semana."""
    return week_monday(parse_date(request.GET.get("as_of", "")) or timezone.localdate())


def week_monday(value: date) -> date:
    """Converte uma referência de semana na segunda-feira canônica."""
    return value - timedelta(days=value.weekday())


def week_navigation(as_of: date) -> tuple[dict[str, object], ...]:
    """Monta os cabeçalhos datados dos cinco dias da semana canônica."""
    return tuple(
        {"day_of_week": day, "label": label, "date": as_of + timedelta(days=offset)}
        for offset, (day, label) in enumerate(ScheduleSelector().day_choices())
    )


def copy_day_initial(as_of: date, day_choices: tuple[tuple[str, str], ...]) -> dict[str, object]:
    """Preenche o formulário de cópia a partir da semana atualmente exibida."""
    source_index = as_of.weekday() if as_of.weekday() < len(day_choices) else 0
    target_index = (source_index + 1) % len(day_choices)
    return {
        "source_day": day_choices[source_index][0],
        "target_day": day_choices[target_index][0],
        "as_of": as_of,
    }


def matrix_context(user, class_id, as_of: date) -> dict[str, object]:
    """Centraliza a projeção da matriz e sua navegação semanal."""
    selector = ScheduleSelector()
    day_choices = selector.day_choices()
    today = timezone.localdate()
    return {
        "class_id": class_id,
        "class_obj": selector.get_class_for_matrix(
            class_id,
            user_id=user.pk,
            role_name=role_name(user),
            as_of=as_of,
        ),
        "as_of": as_of,
        "day_choices": day_choices,
        "week_days": week_navigation(as_of),
        "previous_week": as_of - timedelta(days=7),
        "next_week": as_of + timedelta(days=7),
        "today": week_monday(today),
        "matrix_rows": selector.get_class_matrix(class_id, as_of),
    }


def matrix_url(class_id, as_of: date) -> str:
    """Monta a URL canônica da matriz preservando a vigência selecionada."""
    return f"{reverse('schedule_weekly', args=[class_id])}?as_of={as_of.isoformat()}"


def cell_action_url(route_name: str, *args, as_of: date) -> str:
    """Monta a action POST da célula preservando a referência de vigência."""
    return f"{reverse(route_name, args=args)}?as_of={as_of.isoformat()}"


def is_component_htmx_request(request: HttpRequest) -> bool:
    """Distingue componente HTMX da navegação parcial com documento completo."""
    return bool(request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"))
