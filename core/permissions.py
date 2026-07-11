"""Políticas centrais de papéis, módulos e comandos."""

from __future__ import annotations

ROLE_MODULES: dict[str, frozenset[str]] = {
    "ADMIN": frozenset({"*"}),
    "SECRETARY": frozenset(
        {"students", "guardians", "classes", "enrollments", "addresses", "rooms", "dashboard"}
    ),
    "COORDINATOR": frozenset(
        {
            "teachers",
            "students",
            "guardians",
            "classes",
            "rooms",
            "agenda",
            "activities",
            "academic_calendar",
            "attendance",
            "notifications",
            "dashboard",
        }
    ),
    "TEACHER": frozenset(
        {
            "classes",
            "agenda",
            "activities",
            "attendance",
            "academic_calendar",
            "notifications",
            "dashboard",
        }
    ),
    "FINANCE": frozenset({"financeiro", "students", "classes", "dashboard"}),
    "GUARDIAN": frozenset(
        {"students", "activities", "attendance", "academic_calendar", "notifications", "dashboard"}
    ),
}

DEMO_COMMAND_MODULES = frozenset({"agenda", "activities", "attendance", "classes", "enrollments"})
PUBLIC_VIEW_NAMES = frozenset(
    {
        "index",
        "health",
        "readiness",
        "metrics",
        "login",
        "password_reset",
        "password_reset_done",
        "password_reset_confirm",
        "password_reset_complete",
        "demo_signup",
        "demo_verify",
        "support_access_consume",
    }
)
SELF_SERVICE_METHODS = frozenset(
    {
        "change_password",
        "mark_as_read",
        "mark_all_as_read",
        "submit_justification",
    }
)
GUARDIAN_VIEW_NAMES = frozenset(
    {
        "dashboard",
        "school_dashboard",
        "student_profile",
        "student_attendance",
        "student_attendance_class",
        "justification_create",
        "calendar_month",
        "calendar_month_specific",
        "activities_list",
        "activity_detail",
        "notification_list",
        "notification_mark_read",
        "notification_mark_all_read",
        "unread_count",
        "profile",
        "change_password",
        "logout",
    }
)


def role_name(user) -> str:
    """Retorna o nome do papel sem gerar consulta quando ausente."""
    role = getattr(user, "role", None)
    return getattr(role, "name", "") or ""


def can_access_module(user, app_label: str) -> bool:
    """Verifica acesso de alto nível ao módulo informado."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or getattr(user, "access_mode", "") == "SUPPORT":
        return True
    allowed = ROLE_MODULES.get(role_name(user), frozenset())
    return "*" in allowed or app_label in allowed


def can_execute_service(user, app_label: str, method_name: str) -> bool:
    """Aplica defesa em profundidade aos comandos de services."""
    if user is None or app_label == "audit":
        return True
    if user.is_superuser or getattr(user, "access_mode", "") == "SUPPORT":
        return True
    if method_name in SELF_SERVICE_METHODS:
        return True
    if getattr(user, "access_mode", "") == "DEMO" and app_label not in DEMO_COMMAND_MODULES:
        return False
    return can_access_module(user, app_label)


def modules_for_user(user) -> frozenset[str]:
    """Retorna módulos exibíveis na navegação."""
    if getattr(user, "is_superuser", False) or getattr(user, "access_mode", "") == "SUPPORT":
        return frozenset({"*"})
    return ROLE_MODULES.get(role_name(user), frozenset())
