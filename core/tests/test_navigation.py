"""Testes da composicao da navegacao lateral escolar."""

from types import SimpleNamespace

import pytest
from django.urls import reverse

from core.models import Role
from core.navigation import build_school_navigation


def _user(role_name: str, *, is_staff: bool = False):
    return SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        is_staff=is_staff,
        access_mode="STANDARD",
        role=SimpleNamespace(name=role_name),
    )


def _labels(navigation):
    return {
        group["label"]: [item["label"] for item in group["items"]] for group in navigation["groups"]
    }


@pytest.mark.parametrize(
    ("role_name", "expected_groups"),
    [
        (
            "ADMIN",
            {"Acadêmico", "Secretaria", "Coordenação", "Financeiro", "Administração"},
        ),
        ("COORDINATOR", {"Acadêmico", "Secretaria", "Coordenação"}),
        ("SECRETARY", {"Acadêmico", "Secretaria"}),
        ("TEACHER", {"Rotina Docente", "Planejamento"}),
        ("FINANCE", {"Acadêmico", "Secretaria", "Financeiro"}),
        ("GUARDIAN", {"Acompanhamento"}),
    ],
)
def test_build_school_navigation_filters_groups_by_role(role_name, expected_groups):
    navigation = build_school_navigation(_user(role_name), "dashboard")

    assert set(_labels(navigation)) == expected_groups


def test_build_school_navigation_hides_unauthorized_items():
    labels = _labels(build_school_navigation(_user("FINANCE"), "finance_dashboard"))

    assert labels == {
        "Acadêmico": ["Turmas"],
        "Secretaria": ["Alunos"],
        "Financeiro": ["Visão Financeira"],
    }


@pytest.mark.parametrize(
    ("role_name", "expected"),
    [
        (
            "ADMIN",
            {
                "Acadêmico": [
                    "Turmas",
                    "Disciplinas",
                    "Grade Horária",
                    "Atividades",
                    "Frequência",
                    "Agenda",
                ],
                "Secretaria": [
                    "Professores",
                    "Alunos",
                    "Responsáveis",
                    "Matrículas",
                    "Salas",
                    "Aspectos da rotina",
                ],
                "Coordenação": ["Calendário", "Feriados", "Anos Letivos", "Comunicados"],
                "Financeiro": ["Visão Financeira"],
                "Administração": ["Unidades", "Escola", "Usuários", "Acessos"],
            },
        ),
        (
            "SECRETARY",
            {
                "Acadêmico": ["Turmas"],
                "Secretaria": [
                    "Professores",
                    "Alunos",
                    "Responsáveis",
                    "Matrículas",
                    "Salas",
                    "Aspectos da rotina",
                ],
            },
        ),
        (
            "COORDINATOR",
            {
                "Acadêmico": [
                    "Turmas",
                    "Disciplinas",
                    "Grade Horária",
                    "Atividades",
                    "Frequência",
                    "Agenda",
                ],
                "Secretaria": [
                    "Professores",
                    "Alunos",
                    "Responsáveis",
                    "Aspectos da rotina",
                ],
                "Coordenação": ["Calendário", "Feriados", "Anos Letivos", "Comunicados"],
            },
        ),
        (
            "TEACHER",
            {
                "Rotina Docente": [
                    "Turmas",
                    "Grade Horária",
                    "Atividades",
                    "Frequência",
                    "Agenda",
                ],
                "Planejamento": ["Calendário", "Comunicados"],
            },
        ),
        (
            "GUARDIAN",
            {
                "Acompanhamento": [
                    "Aluno",
                    "Atividades",
                    "Frequência",
                    "Calendário",
                    "Agenda",
                ]
            },
        ),
    ],
)
def test_build_school_navigation_uses_exact_taxonomy(role_name, expected):
    assert _labels(build_school_navigation(_user(role_name), "dashboard")) == expected


@pytest.mark.parametrize(
    ("view_name", "group_label", "item_label"),
    [
        ("teacher_edit", "Secretaria", "Professores"),
        ("student_guardian_link_edit", "Secretaria", "Alunos"),
        ("guardian_edit", "Secretaria", "Responsáveis"),
        ("billing_detail", "Financeiro", "Visão Financeira"),
        ("attendance_record_fill", "Acadêmico", "Frequência"),
        ("event_detail", "Coordenação", "Calendário"),
        ("diary_daily", "Acadêmico", "Agenda"),
        ("rooms_list", "Secretaria", "Salas"),
        ("room_edit", "Secretaria", "Salas"),
        ("diary_configuration", "Secretaria", "Aspectos da rotina"),
        ("diary_aspect_detail", "Secretaria", "Aspectos da rotina"),
        ("diary_aspect_toggle", "Secretaria", "Aspectos da rotina"),
        ("school_settings_edit", "Administração", "Escola"),
    ],
)
def test_build_school_navigation_expands_route_family(view_name, group_label, item_label):
    navigation = build_school_navigation(_user("ADMIN"), view_name)
    expanded = [group for group in navigation["groups"] if group["expanded"]]

    assert len(expanded) == 1
    assert expanded[0]["label"] == group_label
    assert [item["label"] for item in expanded[0]["items"] if item["active"]] == [item_label]
    active_item = next(item for item in expanded[0]["items"] if item["active"])
    assert navigation["active_group_id"] == expanded[0]["id"]
    assert navigation["active_url_name"] == active_item["url_name"]


@pytest.mark.parametrize(
    ("view_name", "item_label"),
    [
        ("teacher_schedule", "Grade Horária"),
        ("student_attendance", "Frequência"),
        ("class_attendance_summary", "Frequência"),
    ],
)
def test_build_school_navigation_avoids_overlapping_route_families(view_name, item_label):
    navigation = build_school_navigation(_user("ADMIN"), view_name)
    active_items = [
        item["label"] for group in navigation["groups"] for item in group["items"] if item["active"]
    ]

    assert active_items == [item_label]
    assert sum(group["expanded"] for group in navigation["groups"]) == 1


def test_build_school_navigation_adds_executive_only_for_staff():
    regular = build_school_navigation(_user("ADMIN"), "dashboard")
    staff = build_school_navigation(_user("ADMIN", is_staff=True), "executive_dashboard")

    assert [link["label"] for link in regular["direct_links"]] == ["Visão geral"]
    assert [link["label"] for link in staff["direct_links"]] == ["Visão geral", "Executivo"]
    assert staff["direct_links"][1]["active"] is True


def test_guardian_navigation_does_not_expose_announcements():
    labels = _labels(build_school_navigation(_user("GUARDIAN"), "calendar_month"))

    assert "Comunicados" not in labels["Acompanhamento"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "url_name"),
    [
        (Role.Name.SECRETARY, "teachers_list"),
        (Role.Name.SECRETARY, "rooms_list"),
        (Role.Name.SECRETARY, "diary_configuration"),
        (Role.Name.COORDINATOR, "holidays_list"),
        (Role.Name.TEACHER, "announcement_list"),
        (Role.Name.FINANCE, "finance_dashboard"),
        (Role.Name.GUARDIAN, "calendar_month"),
    ],
)
def test_rendered_navigation_destinations_are_authorized(client, user, role, url_name):
    role_obj, _ = Role.objects.get_or_create(name=role)
    user.role = role_obj
    user.is_superuser = False
    user.is_staff = False
    user.save(update_fields=["role", "is_superuser", "is_staff"])
    client.force_login(user)

    assert client.get(reverse(url_name)).status_code == 200


@pytest.mark.django_db
def test_school_navigation_renders_accessible_accordion(client, user):
    role, _ = Role.objects.get_or_create(name=Role.Name.COORDINATOR)
    user.role = role
    user.is_superuser = False
    user.is_staff = False
    user.save(update_fields=["role", "is_superuser", "is_staff"])
    client.force_login(user)

    response = client.get(reverse("activities_list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert content.count('class="nxl-link sm-nav-group-toggle"') == 3
    assert content.count("active nxl-trigger") == 1
    assert 'aria-expanded="true"' in content
    assert 'aria-controls="school-nav-group-0"' in content
    assert 'aria-current="page"' in content


@pytest.mark.django_db
def test_school_navigation_uses_canonical_overview_link(client, user):
    role, _ = Role.objects.get_or_create(name=Role.Name.ADMIN)
    user.role = role
    user.save(update_fields=["role"])
    client.force_login(user)

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert f'href="{reverse("dashboard")}"' in content
    assert 'href="/dashboard/"' not in content
    assert 'id="app-main"' in content
    assert "hx-history-elt" in content
    assert '<ul class="nxl-navbar" id="school-navigation">' in content
    assert 'hx-target="#app-main"' in content
    assert 'hx-select="#app-main"' in content
    assert "hx-select-oob" not in content
    assert 'hx-swap="outerHTML transition:true show:top"' in content
    assert 'hx-push-url="true"' in content
    assert 'hx-indicator="#app-navigation-progress"' in content
    assert 'sidebarContent.addEventListener("focusin"' in content
    assert 'scrollIntoView({block: "nearest", inline: "nearest"})' in content
    assert "applySchoolNavigationState();" in content


@pytest.mark.django_db
def test_school_navigation_boosted_response_keeps_full_fallback_document(client, user):
    role, _ = Role.objects.get_or_create(name=Role.Name.COORDINATOR)
    user.role = role
    user.is_superuser = False
    user.save(update_fields=["role", "is_superuser"])
    client.force_login(user)

    response = client.get(
        reverse("activities_list"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_BOOSTED="true",
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "<!DOCTYPE html>" in content
    assert 'id="app-main"' in content
    assert 'id="school-navigation"' in content
    assert 'data-nav-group-id="school-nav-group-0"' in content
    assert 'data-nav-url-name="activities_list"' in content
    assert content.count("active nxl-trigger") == 1
    assert 'aria-current="page"' in content


@pytest.mark.django_db
def test_school_navigation_does_not_change_component_htmx_responses(client, user):
    role, _ = Role.objects.get_or_create(name=Role.Name.COORDINATOR)
    user.role = role
    user.is_superuser = False
    user.save(update_fields=["role", "is_superuser"])
    client.force_login(user)

    response = client.get(reverse("activities_list"), HTTP_HX_REQUEST="true")
    content = response.content.decode()

    assert response.status_code == 200
    assert "<!DOCTYPE html>" not in content
    assert 'id="app-main"' not in content
    assert 'class="table table-hover mb-0"' in content
