"""Testes de renderização das listas do calendário."""

import pytest
from django.urls import reverse

from academic_calendar.models import CalendarEvent, Holiday


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url_name", "target"),
    [
        ("events_list", b"Lista de Eventos"),
        ("holidays_list", b"Lista de Feriados"),
        ("academic_years_list", b"Lista de Anos Letivos"),
    ],
)
def test_calendar_lists_render_shared_header_and_htmx(client, user, url_name, target):
    client.force_login(user)
    url = reverse(url_name)

    response = client.get(url)
    partial_response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert target in response.content
    assert partial_response.status_code == 200
    assert b"<html" not in partial_response.content


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["holiday_create", "academic_year_create"])
def test_calendar_create_forms_use_compact_card(client, user, url_name):
    client.force_login(user)

    response = client.get(reverse(url_name))

    assert response.status_code == 200
    assert b"col-12 col-xl-5" in response.content
    assert b"row g-2" in response.content


@pytest.mark.django_db
def test_event_create_renders_compact_form_in_day_agenda_for_htmx(client, user):
    client.force_login(user)

    response = client.get(reverse("event_create"), {"date": "2026-07-10"}, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b'id="calendar-day-agenda"' in response.content
    assert b"row g-2" in response.content


@pytest.mark.django_db
def test_calendar_day_agenda_includes_events_and_holidays(client, user):
    client.force_login(user)
    selected_date = "2026-07-10"
    CalendarEvent.objects.create(
        title="Reunião pedagógica",
        start_date="2026-07-10",
        end_date="2026-07-10",
        type=CalendarEvent.Type.MEETING,
        created_by=user,
        updated_by=user,
    )
    Holiday.objects.create(
        name="Feriado local",
        date="2020-07-10",
        is_recurring=True,
        created_by=user,
        updated_by=user,
    )

    response = client.get(
        reverse("calendar_month_specific", kwargs={"year": 2026, "month": 7}),
        {"selected_date": selected_date},
    )
    partial_response = client.get(
        reverse("calendar_month_specific", kwargs={"year": 2026, "month": 7}),
        {"selected_date": selected_date},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Reuni" in response.content
    assert b"Feriado local" in response.content
    assert partial_response.status_code == 200
    assert b"calendar-workspace" in partial_response.content


@pytest.mark.django_db
def test_base_template_renders_accessible_theme_toggle(client, user):
    client.force_login(user)

    response = client.get(reverse("calendar_month"))

    assert response.status_code == 200
    assert b'id="theme-toggle"' in response.content
    assert b'aria-label="Ativar modo escuro"' in response.content
    assert b"app-skin-dark" in response.content
