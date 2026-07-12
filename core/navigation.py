"""Composição da navegação lateral escolar por público, papel e rota ativa."""

from __future__ import annotations

from typing import Any

from core.permissions import can_access_module, role_name

ADMIN = "ADMIN"
SECRETARY = "SECRETARY"
COORDINATOR = "COORDINATOR"
TEACHER = "TEACHER"
FINANCE = "FINANCE"
GUARDIAN = "GUARDIAN"


STAFF_NAVIGATION = (
    {
        "label": "Acadêmico",
        "icon": "feather-book-open",
        "items": (
            {
                "label": "Turmas",
                "icon": "feather-layers",
                "url_name": "classes_list",
                "module": "classes",
                "roles": (ADMIN, SECRETARY, COORDINATOR),
                "prefixes": ("class_", "classes_"),
                "excluded_routes": ("class_attendance_summary",),
            },
            {
                "label": "Disciplinas",
                "icon": "feather-book",
                "url_name": "subjects_list",
                "module": "teachers",
                "roles": (ADMIN, COORDINATOR),
                "prefixes": ("subject_", "subjects_"),
            },
            {
                "label": "Grade Horária",
                "icon": "feather-clock",
                "url_name": "time_slots_list",
                "module": "agenda",
                "roles": (ADMIN, COORDINATOR),
                "prefixes": ("time_slot_", "time_slots_", "schedule_", "teacher_schedule"),
            },
            {
                "label": "Atividades",
                "icon": "feather-edit-3",
                "url_name": "activities_list",
                "module": "activities",
                "roles": (ADMIN, COORDINATOR),
                "prefixes": ("activity_", "activities_"),
            },
            {
                "label": "Frequência",
                "icon": "feather-check-circle",
                "url_name": "attendance_records_list",
                "module": "attendance",
                "roles": (ADMIN, COORDINATOR),
                "prefixes": (
                    "attendance_",
                    "class_attendance_",
                    "student_attendance",
                    "students_at_risk",
                    "justification_",
                    "justifications_",
                ),
            },
        ),
    },
    {
        "label": "Secretaria",
        "icon": "feather-file-text",
        "items": (
            {
                "label": "Professores",
                "icon": "feather-user-check",
                "url_name": "teachers_list",
                "module": "teachers",
                "roles": (ADMIN, SECRETARY, COORDINATOR),
                "prefixes": ("teacher_",),
                "excluded_routes": ("teacher_schedule",),
            },
            {
                "label": "Alunos",
                "icon": "feather-user",
                "url_name": "students_list",
                "module": "students",
                "roles": (ADMIN, SECRETARY, COORDINATOR),
                "prefixes": ("student_", "students_"),
                "excluded_routes": ("student_attendance", "student_attendance_class"),
            },
            {
                "label": "Responsáveis",
                "icon": "feather-users",
                "url_name": "guardians_list",
                "module": "guardians",
                "roles": (ADMIN, SECRETARY, COORDINATOR),
                "prefixes": ("guardian_", "guardians_"),
            },
            {
                "label": "Matrículas",
                "icon": "feather-clipboard",
                "url_name": "secretary_dashboard",
                "module": "enrollments",
                "roles": (ADMIN, SECRETARY),
                "routes": ("secretary_dashboard",),
                "prefixes": ("application_", "document_", "bulk_reenroll", "notify_"),
            },
        ),
    },
    {
        "label": "Coordenação",
        "icon": "feather-compass",
        "items": (
            {
                "label": "Calendário",
                "icon": "feather-calendar",
                "url_name": "calendar_month",
                "module": "academic_calendar",
                "roles": (ADMIN, COORDINATOR),
                "prefixes": ("calendar_", "event_", "events_"),
            },
            {
                "label": "Feriados",
                "icon": "feather-flag",
                "url_name": "holidays_list",
                "module": "academic_calendar",
                "roles": (ADMIN, COORDINATOR),
                "prefixes": ("holiday_", "holidays_"),
            },
            {
                "label": "Anos Letivos",
                "icon": "feather-calendar",
                "url_name": "academic_years_list",
                "module": "academic_calendar",
                "roles": (ADMIN, COORDINATOR),
                "prefixes": ("academic_year_", "academic_years_"),
            },
            {
                "label": "Comunicados",
                "icon": "feather-message-square",
                "url_name": "announcement_list",
                "module": "notifications",
                "roles": (ADMIN, COORDINATOR),
                "prefixes": ("announcement_",),
            },
        ),
    },
    {
        "label": "Financeiro",
        "icon": "feather-credit-card",
        "items": (
            {
                "label": "Visão Financeira",
                "icon": "feather-bar-chart-2",
                "url_name": "finance_dashboard",
                "module": "financeiro",
                "roles": (ADMIN, FINANCE),
                "prefixes": ("finance_", "plan_", "billing_", "bulk_generate_"),
            },
        ),
    },
    {
        "label": "Administração",
        "icon": "feather-settings",
        "items": (
            {
                "label": "Salas",
                "icon": "feather-home",
                "url_name": "rooms_list",
                "module": "rooms",
                "roles": (ADMIN,),
                "prefixes": ("room_", "rooms_"),
            },
            {
                "label": "Unidades",
                "icon": "feather-briefcase",
                "url_name": "business_unit_list",
                "module": "core",
                "roles": (ADMIN,),
                "prefixes": ("business_unit_",),
            },
            {
                "label": "Escola",
                "icon": "feather-home",
                "url_name": "school_settings_detail",
                "module": "core",
                "roles": (ADMIN,),
                "routes": ("school_detail", "school_edit"),
                "prefixes": ("school_settings_",),
            },
            {
                "label": "Usuários",
                "icon": "feather-users",
                "url_name": "users_list",
                "module": "core",
                "roles": (ADMIN,),
                "prefixes": ("user_", "users_"),
            },
        ),
    },
)


TEACHER_NAVIGATION = (
    {
        "label": "Rotina Docente",
        "icon": "feather-edit-3",
        "items": (
            {
                "label": "Turmas",
                "icon": "feather-layers",
                "url_name": "classes_list",
                "module": "classes",
                "roles": (TEACHER,),
                "prefixes": ("class_", "classes_"),
                "excluded_routes": ("class_attendance_summary",),
            },
            {
                "label": "Grade Horária",
                "icon": "feather-clock",
                "url_name": "time_slots_list",
                "module": "agenda",
                "roles": (TEACHER,),
                "prefixes": ("time_slot_", "time_slots_", "schedule_", "teacher_schedule"),
            },
            {
                "label": "Atividades",
                "icon": "feather-edit-3",
                "url_name": "activities_list",
                "module": "activities",
                "roles": (TEACHER,),
                "prefixes": ("activity_", "activities_"),
            },
            {
                "label": "Frequência",
                "icon": "feather-check-circle",
                "url_name": "attendance_records_list",
                "module": "attendance",
                "roles": (TEACHER,),
                "prefixes": (
                    "attendance_",
                    "class_attendance_",
                    "student_attendance",
                    "students_at_risk",
                    "justification_",
                    "justifications_",
                ),
            },
        ),
    },
    {
        "label": "Planejamento",
        "icon": "feather-calendar",
        "items": (
            {
                "label": "Calendário",
                "icon": "feather-calendar",
                "url_name": "calendar_month",
                "module": "academic_calendar",
                "roles": (TEACHER,),
                "prefixes": ("calendar_", "event_", "events_", "holiday_", "holidays_"),
            },
            {
                "label": "Comunicados",
                "icon": "feather-message-square",
                "url_name": "announcement_list",
                "module": "notifications",
                "roles": (TEACHER,),
                "prefixes": ("announcement_",),
            },
        ),
    },
)


GUARDIAN_NAVIGATION = (
    {
        "label": "Acompanhamento",
        "icon": "feather-heart",
        "items": (
            {
                "label": "Aluno",
                "icon": "feather-user",
                "url_name": "dashboard",
                "ignore_url_name": True,
                "module": "students",
                "roles": (GUARDIAN,),
                "prefixes": ("student_",),
                "excluded_routes": ("student_attendance", "student_attendance_class"),
            },
            {
                "label": "Atividades",
                "icon": "feather-edit-3",
                "url_name": "activities_list",
                "module": "activities",
                "roles": (GUARDIAN,),
                "prefixes": ("activity_", "activities_"),
            },
            {
                "label": "Frequência",
                "icon": "feather-check-circle",
                "url_name": "dashboard",
                "ignore_url_name": True,
                "module": "attendance",
                "roles": (GUARDIAN,),
                "prefixes": ("student_attendance", "justification_", "justifications_"),
            },
            {
                "label": "Calendário",
                "icon": "feather-calendar",
                "url_name": "calendar_month",
                "module": "academic_calendar",
                "roles": (GUARDIAN,),
                "prefixes": ("calendar_",),
            },
        ),
    },
)


def _is_active(item: dict[str, Any], view_name: str) -> bool:
    """Indica se a rota pertence exclusivamente à família do item."""
    if view_name in item.get("excluded_routes", ()):
        return False
    routes = item.get("routes", ())
    prefixes = item.get("prefixes", ())
    url_matches = not item.get("ignore_url_name", False) and view_name == item["url_name"]
    return url_matches or view_name in routes or view_name.startswith(prefixes)


def _catalog_for(user) -> tuple[dict[str, Any], ...]:
    """Seleciona a taxonomia adequada ao público autenticado."""
    role = role_name(user)
    if role == TEACHER:
        return TEACHER_NAVIGATION
    if role == GUARDIAN:
        return GUARDIAN_NAVIGATION
    return STAFF_NAVIGATION


def _can_show_item(user, item: dict[str, Any]) -> bool:
    """Combina papel explícito e permissão de módulo."""
    if getattr(user, "is_superuser", False) or getattr(user, "access_mode", "") == "SUPPORT":
        return can_access_module(user, item["module"])
    return role_name(user) in item.get("roles", ()) and can_access_module(user, item["module"])


def build_school_navigation(user, view_name: str) -> dict[str, Any]:
    """Retorna links e grupos autorizados com o estado da rota corrente."""
    direct_links = [
        {
            "label": "Visão geral",
            "icon": "feather-airplay",
            "url_name": "dashboard",
            "active": view_name in {"dashboard", "school_dashboard"},
        }
    ]
    if getattr(user, "is_staff", False):
        direct_links.append(
            {
                "label": "Executivo",
                "icon": "feather-bar-chart-2",
                "url_name": "executive_dashboard",
                "active": view_name == "executive_dashboard",
            }
        )

    groups = []
    for index, group in enumerate(_catalog_for(user)):
        items = [
            {**item, "active": _is_active(item, view_name)}
            for item in group["items"]
            if _can_show_item(user, item)
        ]
        if not items:
            continue
        groups.append(
            {
                "id": f"school-nav-group-{index}",
                "label": group["label"],
                "icon": group["icon"],
                "items": items,
                "expanded": any(item["active"] for item in items),
            }
        )
    active_direct = next((link for link in direct_links if link["active"]), None)
    active_group = next((group for group in groups if group["expanded"]), None)
    active_item = (
        next((item for item in active_group["items"] if item["active"]), None)
        if active_group
        else None
    )
    return {
        "direct_links": direct_links,
        "groups": groups,
        "active_group_id": active_group["id"] if active_group else "",
        "active_url_name": (active_item or active_direct or {}).get("url_name", ""),
    }
