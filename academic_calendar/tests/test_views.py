"""Testes de renderização das listas do calendário."""

import datetime as dt

import pytest
from django.urls import reverse

from academic_calendar.models import AcademicYear, CalendarEvent, Holiday
from academic_calendar.services import CalendarService
from base.exceptions import PermissionDeniedError


def _create_role_user(role_name: str, email: str):
    from core.models import CustomUser, Role

    role = Role.objects.get(name=role_name)
    return CustomUser.objects.create_user(
        email=email,
        password="Senha123",
        first_name="Teste",
        last_name="Calendário",
        role=role,
    )


def _set_access(user, module_key: str, actions: set[str]) -> None:
    from core.access_catalog import ACTION_FIELDS
    from core.models import RoleModuleAccess

    access = RoleModuleAccess.objects.get(role=user.role, module_key=module_key)
    for action, field in ACTION_FIELDS.items():
        setattr(access, field, action in actions)
    access.save()
    if hasattr(user, "_role_access_cache"):
        del user._role_access_cache


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
@pytest.mark.parametrize("role_name", ["TEACHER", "GUARDIAN"])
@pytest.mark.parametrize("url_name", ["holidays_list", "academic_years_list"])
def test_calendar_management_denies_teacher_and_guardian(client, role_name, url_name):
    restricted_user = _create_role_user(
        role_name,
        f"{role_name.lower()}-{url_name}@calendar.test",
    )
    client.force_login(restricted_user)

    assert client.get(reverse(url_name)).status_code == 403


@pytest.mark.django_db
def test_holidays_view_only_hides_mutation_controls_and_isolated_routes(client, user):
    secretary = _create_role_user("SECRETARY", "secretary-holidays-view@calendar.test")
    _set_access(secretary, "holidays", {"view"})
    holiday = Holiday.objects.create(
        name="Feriado somente leitura",
        date="2026-08-15",
        type=Holiday.Type.SCHOOL,
        created_by=user,
        updated_by=user,
    )
    client.force_login(secretary)

    response = client.get(reverse("holidays_list"))

    assert response.status_code == 200
    assert reverse("holiday_create") not in response.content.decode()
    assert reverse("holiday_edit", args=[holiday.pk]) not in response.content.decode()
    assert client.get(reverse("holiday_create")).status_code == 403
    assert client.get(reverse("holiday_edit", args=[holiday.pk])).status_code == 403
    assert client.get(reverse("academic_years_list")).status_code == 403
    assert client.get(reverse("calendar_month")).status_code == 403


@pytest.mark.django_db
def test_academic_years_view_only_hides_mutation_controls_and_isolated_routes(client, user):
    secretary = _create_role_user("SECRETARY", "secretary-years-view@calendar.test")
    _set_access(secretary, "academic_years", {"view"})
    academic_year = AcademicYear.objects.create(
        name="Ano somente leitura",
        start_date="2029-02-01",
        end_date="2029-12-15",
        created_by=user,
        updated_by=user,
    )
    client.force_login(secretary)

    response = client.get(reverse("academic_years_list"))

    assert response.status_code == 200
    assert reverse("academic_year_create") not in response.content.decode()
    assert reverse("academic_year_edit", args=[academic_year.pk]) not in response.content.decode()
    assert client.get(reverse("academic_year_create")).status_code == 403
    assert client.get(reverse("academic_year_edit", args=[academic_year.pk])).status_code == 403
    assert client.get(reverse("holidays_list")).status_code == 403
    assert client.get(reverse("calendar_month")).status_code == 403


@pytest.mark.django_db
def test_calendar_service_enforces_separate_management_permissions():
    secretary = _create_role_user("SECRETARY", "secretary-calendar-service@calendar.test")
    _set_access(secretary, "holidays", {"view", "create"})
    service = CalendarService(user=secretary)

    holiday = service.create_holiday(
        {
            "name": "Feriado autorizado",
            "date": dt.date(2026, 9, 8),
            "type": Holiday.Type.SCHOOL,
        }
    )
    with pytest.raises(PermissionDeniedError):
        service.update_holiday(
            holiday.pk,
            {
                "name": "Alteração negada",
                "date": holiday.date,
                "type": holiday.type,
            },
        )
    with pytest.raises(PermissionDeniedError):
        service.create_academic_year(
            {
                "name": "2028",
                "start_date": dt.date(2028, 2, 1),
                "end_date": dt.date(2028, 12, 15),
            }
        )

    _set_access(secretary, "holidays", {"view", "edit"})
    _set_access(secretary, "academic_years", {"view", "create"})
    academic_year = service.create_academic_year(
        {
            "name": "2028",
            "start_date": dt.date(2028, 2, 1),
            "end_date": dt.date(2028, 12, 15),
        }
    )
    service.update_holiday(
        holiday.pk,
        {
            "name": "Feriado atualizado",
            "date": holiday.date,
            "type": holiday.type,
        },
    )
    with pytest.raises(PermissionDeniedError):
        service.update_academic_year(
            academic_year.pk,
            {
                "name": academic_year.name,
                "start_date": academic_year.start_date,
                "end_date": academic_year.end_date,
                "status": academic_year.status,
            },
        )

    holiday.refresh_from_db()
    assert holiday.name == "Feriado atualizado"
    assert AcademicYear.objects.filter(name="2028").exists() is True


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


@pytest.mark.django_db
def test_holiday_create_and_edit_views_persist_changes(client, user):
    client.force_login(user)
    create_response = client.post(
        reverse("holiday_create"),
        {
            "name": "Feriado Municipal",
            "date": "2026-07-20",
            "type": Holiday.Type.MUNICIPAL,
            "is_recurring": "on",
        },
    )
    holiday = Holiday.objects.get(name="Feriado Municipal")

    edit_response = client.post(
        reverse("holiday_edit", args=[holiday.pk]),
        {
            "name": "Feriado Local",
            "date": "2026-07-20",
            "type": Holiday.Type.SCHOOL,
            "is_recurring": "on",
            "version": holiday.version,
        },
    )

    holiday.refresh_from_db()
    assert create_response.status_code == 302
    assert edit_response.status_code == 302
    assert holiday.name == "Feriado Local"


@pytest.mark.django_db
def test_academic_year_create_and_edit_views_persist_changes(client, user):
    client.force_login(user)
    create_response = client.post(
        reverse("academic_year_create"),
        {
            "name": "Ano 2027",
            "start_date": "2027-01-20",
            "end_date": "2027-12-10",
            "status": AcademicYear.Status.PLANNED,
        },
    )
    academic_year = AcademicYear.objects.get(name="Ano 2027")
    edit_response = client.post(
        reverse("academic_year_edit", args=[academic_year.pk]),
        {
            "name": "Ano Letivo 2027",
            "start_date": "2027-01-20",
            "end_date": "2027-12-10",
            "status": AcademicYear.Status.IN_PROGRESS,
            "version": academic_year.version,
        },
    )

    academic_year.refresh_from_db()
    assert create_response.status_code == 302
    assert edit_response.status_code == 302
    assert academic_year.status == AcademicYear.Status.IN_PROGRESS


@pytest.mark.django_db
def test_event_create_detail_edit_and_cancel_views(client, user):
    client.force_login(user)
    payload = {
        "title": "Reunião de responsáveis",
        "description": "Apresentação",
        "start_date": "2026-08-10",
        "end_date": "2026-08-10",
        "type": CalendarEvent.Type.MEETING,
        "audience": CalendarEvent.Audience.GUARDIANS,
        "class_obj": "",
        "is_public": "on",
    }
    create_response = client.post(reverse("event_create"), payload, HTTP_HX_REQUEST="true")
    event = CalendarEvent.objects.get(title="Reunião de responsáveis")
    detail_response = client.get(
        reverse("event_detail", args=[event.pk]),
        {"selected_date": "inválida"},
        HTTP_HX_REQUEST="true",
    )

    edit_payload = {
        **payload,
        "title": "Reunião pedagógica",
        "version": event.version,
    }
    edit_response = client.post(
        reverse("event_edit", args=[event.pk]),
        edit_payload,
        HTTP_HX_REQUEST="true",
    )
    cancel_response = client.post(
        reverse("event_cancel", args=[event.pk]),
        {"reason": "Reagendamento"},
    )

    event.refresh_from_db()
    assert create_response.status_code == 200
    assert detail_response.status_code == 200
    assert edit_response.status_code == 200
    assert cancel_response.status_code == 302
    assert event.title == "Reunião pedagógica"
    assert event.is_cancelled is True


@pytest.mark.django_db
def test_calendar_helpers_handle_invalid_dates_and_component_request(client, user):
    client.force_login(user)
    url = reverse("calendar_month_specific", kwargs={"year": 2026, "month": 7})

    response = client.get(
        url,
        {"selected_date": "invalid", "component": "agenda"},
        HTTP_HX_REQUEST="true",
    )
    create_response = client.get(
        reverse("event_create"),
        {"date": "invalid"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"calendar-day-agenda" in response.content
    assert create_response.status_code == 200
