"""Composicao da navegacao lateral escolar por perfil e rota ativa."""

from __future__ import annotations

from typing import Any

from core.permissions import can_access_module

SCHOOL_NAVIGATION = (
    {
        "label": "Acadêmico",
        "icon": "feather-book-open",
        "items": (
            {
                "label": "Professores",
                "icon": "feather-user-check",
                "url_name": "teachers_list",
                "module": "teachers",
                "prefixes": ("teacher_",),
                "excluded_routes": ("teacher_schedule",),
            },
            {
                "label": "Disciplinas",
                "icon": "feather-book",
                "url_name": "subjects_list",
                "module": "teachers",
                "prefixes": ("subject_", "subjects_"),
            },
            {
                "label": "Alunos e Responsáveis",
                "icon": "feather-users",
                "url_name": "students_list",
                "module": "students",
                "prefixes": ("student_", "students_", "guardian_", "guardians_"),
                "excluded_routes": ("student_attendance", "student_attendance_class"),
            },
            {
                "label": "Turmas",
                "icon": "feather-layers",
                "url_name": "classes_list",
                "module": "classes",
                "prefixes": ("class_", "classes_"),
                "excluded_routes": ("class_attendance_summary",),
            },
            {
                "label": "Salas",
                "icon": "feather-home",
                "url_name": "rooms_list",
                "module": "rooms",
                "prefixes": ("room_", "rooms_"),
            },
        ),
    },
    {
        "label": "Secretaria",
        "icon": "feather-file-text",
        "items": (
            {
                "label": "Matrículas",
                "icon": "feather-clipboard",
                "url_name": "secretary_dashboard",
                "module": "enrollments",
                "routes": ("secretary_dashboard",),
                "prefixes": ("application_", "document_", "bulk_reenroll", "notify_"),
            },
            {
                "label": "Financeiro",
                "icon": "feather-credit-card",
                "url_name": "finance_dashboard",
                "module": "financeiro",
                "prefixes": ("finance_", "plan_", "billing_", "bulk_generate_"),
            },
        ),
    },
    {
        "label": "Coordenação",
        "icon": "feather-compass",
        "items": (
            {
                "label": "Atividades",
                "icon": "feather-edit-3",
                "url_name": "activities_list",
                "module": "activities",
                "prefixes": ("activity_", "activities_"),
            },
            {
                "label": "Frequência",
                "icon": "feather-check-circle",
                "url_name": "attendance_records_list",
                "module": "attendance",
                "prefixes": (
                    "attendance_",
                    "class_attendance_",
                    "student_attendance",
                    "students_at_risk",
                    "justification_",
                    "justifications_",
                ),
            },
            {
                "label": "Grade Horária",
                "icon": "feather-clock",
                "url_name": "time_slots_list",
                "module": "agenda",
                "prefixes": ("time_slot_", "time_slots_", "schedule_", "teacher_schedule"),
            },
            {
                "label": "Calendário",
                "icon": "feather-calendar",
                "url_name": "calendar_month",
                "module": "academic_calendar",
                "prefixes": ("calendar_", "event_", "events_"),
            },
            {
                "label": "Feriados",
                "icon": "feather-flag",
                "url_name": "holidays_list",
                "module": "academic_calendar",
                "prefixes": ("holiday_", "holidays_"),
            },
            {
                "label": "Anos Letivos",
                "icon": "feather-calendar",
                "url_name": "academic_years_list",
                "module": "academic_calendar",
                "prefixes": ("academic_year_", "academic_years_"),
            },
            {
                "label": "Comunicados",
                "icon": "feather-message-square",
                "url_name": "announcement_list",
                "module": "notifications",
                "prefixes": ("announcement_",),
            },
        ),
    },
    {
        "label": "Administração",
        "icon": "feather-settings",
        "items": (
            {
                "label": "Unidades",
                "icon": "feather-briefcase",
                "url_name": "business_unit_list",
                "module": "core",
                "prefixes": ("business_unit_",),
            },
            {
                "label": "Escola",
                "icon": "feather-home",
                "url_name": "school_settings_detail",
                "module": "core",
                "routes": ("school_detail", "school_edit"),
                "prefixes": ("school_settings_",),
            },
            {
                "label": "Usuários",
                "icon": "feather-users",
                "url_name": "users_list",
                "module": "core",
                "prefixes": ("user_", "users_"),
            },
        ),
    },
)


def _is_active(item: dict[str, Any], view_name: str) -> bool:
    if view_name in item.get("excluded_routes", ()):
        return False
    routes = item.get("routes", ())
    prefixes = item.get("prefixes", ())
    return view_name == item["url_name"] or view_name in routes or view_name.startswith(prefixes)


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
    for index, group in enumerate(SCHOOL_NAVIGATION):
        items = []
        for item in group["items"]:
            if not can_access_module(user, item["module"]):
                continue
            items.append({**item, "active": _is_active(item, view_name)})
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
