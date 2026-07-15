"""Fonte única de autorização por papel, módulo, ação e escopo."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from core.access_catalog import (
    ACTIONS,
    ADMIN,
    CREATE,
    DEACTIVATE,
    EDIT,
    MODULES,
    MODULES_BY_KEY,
    TEACHER,
    VIEW,
    action_for_operation,
    default_actions,
    module_for_app,
)

DEMO_COMMAND_MODULES = frozenset(
    {"schedule", "activities", "attendance", "student_diary", "classes", "enrollments"}
)
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
        "teacher_invitation",
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
SELF_SERVICE_VIEW_NAMES = frozenset(
    {
        "profile",
        "change_password",
        "logout",
        "notification_mark_read",
        "notification_mark_all_read",
        "unread_count",
    }
)
GUARDIAN_VIEW_NAMES = frozenset(
    {
        "dashboard",
        "student_profile",
        "student_attendance",
        "student_attendance_class",
        "justification_create",
        "justification_document",
        "calendar_month",
        "calendar_month_specific",
        "activities_list",
        "activity_detail",
        "diary_student_history",
        "notification_list",
        "notification_mark_read",
        "notification_mark_all_read",
        "unread_count",
        "profile",
        "change_password",
        "logout",
    }
)

_SERVICE_CLASS_MODULES = {
    "SubjectService": "subjects",
    "ScheduleService": "schedule",
    "AccessConfigurationService": "__admin__",
    "BusinessUnitService": "__admin__",
    "SchoolService": "__admin__",
    "AccountService": "__admin__",
    "PlatformSchoolService": "__admin__",
}
_SYSTEM_SERVICE_METHODS = frozenset(
    {"create_notification", "create_notifications_bulk", "log_delivery"}
)

_ViewCallable = TypeVar("_ViewCallable", bound=Callable)


def role_name(user) -> str:
    """Retorna o nome do papel sem gerar consulta quando ausente."""
    role = getattr(user, "role", None)
    return getattr(role, "name", "") or ""


def has_unrestricted_tenant_access(user) -> bool:
    """Indica administrador escolar irrestrito, sem ampliar acesso ao schema público."""
    from base import context

    return (
        getattr(user, "is_authenticated", False)
        and role_name(user) == ADMIN
        and context.current_tenant.get() not in {"", "public"}
    )


def can_access(user, module_key: str, action: str = VIEW) -> bool:
    """Verifica a capacidade persistida, negando chaves desconhecidas."""
    if not getattr(user, "is_authenticated", False) or action not in ACTIONS:
        return False
    if getattr(user, "is_superuser", False) or role_name(user) == ADMIN:
        return True
    if module_key == "__admin__" or module_key not in MODULES_BY_KEY:
        return False

    current_role = role_name(user)
    module = MODULES_BY_KEY[module_key]
    if current_role not in module.eligible_roles or action not in module.supported_actions:
        return False

    role = getattr(user, "role", None)
    role_id = getattr(role, "pk", None)
    if role_id is None:
        return action in default_actions(module_key, current_role)

    cache = getattr(user, "_role_access_cache", None)
    if cache is None:
        from core.access.selectors import AccessConfigurationSelector

        cache = AccessConfigurationSelector.permissions_for_role(role_id)
        user._role_access_cache = cache
    return action in cache.get(module_key, frozenset())


def can_access_module(user, app_label: str) -> bool:
    """Compatibilidade pública: acesso ao módulo equivale a Visualizar."""
    module_key = app_label if app_label in MODULES_BY_KEY else module_for_app(app_label)
    return bool(module_key and can_access(user, module_key, VIEW))


def access_policy(module_key: str, action: str) -> Callable[[_ViewCallable], _ViewCallable]:
    """Declara de forma explícita a capacidade exigida por uma view."""
    if module_key != "__admin__" and module_key not in MODULES_BY_KEY:
        raise ValueError(f"Módulo de acesso desconhecido: {module_key}")
    if action not in ACTIONS:
        raise ValueError(f"Ação de acesso desconhecida: {action}")

    def decorate(view_func: _ViewCallable) -> _ViewCallable:
        view_func.access_module = module_key
        view_func.access_action = action
        return view_func

    return decorate


def resolve_view_access(
    view_func,
    view_name: str,
    request_method: str,
    view_kwargs: dict | None = None,
) -> tuple[str | None, str]:
    """Resolve a declaração central de uma rota existente."""
    explicit_module = getattr(view_func, "access_module", None)
    explicit_action = getattr(view_func, "access_action", None)
    if explicit_module:
        return explicit_module, explicit_action or VIEW

    app_label = view_func.__module__.split(".", maxsplit=1)[0]
    if app_label == "teachers" and view_name.startswith("subject"):
        module_key = "subjects"
    elif app_label in {"core", "accounts", "tenancy"}:
        module_key = "dashboard" if view_name == "dashboard" else "__admin__"
    elif app_label == "addresses":
        entity_type = (view_kwargs or {}).get("entity_type", "")
        address_id = (view_kwargs or {}).get("address_id")
        if not entity_type and address_id:
            from addresses.selectors import AddressSelector

            selector = AddressSelector()
            address = selector.get_by_id(address_id)
            entity_type, _ = selector.get_entity_context(address)
        module_key = {
            "teacher": "teachers",
            "guardian": "guardians",
            "student": "students",
            "school": "__admin__",
            "business_unit": "__admin__",
        }.get(entity_type, "students")
    else:
        module_key = module_for_app(app_label)
    action = action_for_operation(
        view_name,
        is_post=request_method.upper() not in {"GET", "HEAD", "OPTIONS"},
    )
    return module_key, action


def can_execute_service(
    user,
    app_label: str,
    method_name: str,
    service_name: str = "",
) -> bool:
    """Aplica a mesma matriz aos comandos de services."""
    if user is None or app_label == "audit" or method_name in _SYSTEM_SERVICE_METHODS:
        return True
    if getattr(user, "is_superuser", False) or role_name(user) == ADMIN:
        return True
    if method_name in SELF_SERVICE_METHODS:
        return True

    module_key = _SERVICE_CLASS_MODULES.get(service_name)
    if module_key is None:
        module_key = module_for_app(
            app_label,
            subject=service_name == "SubjectService" or "subject" in method_name,
        )
    if module_key is None and app_label == "addresses":
        module_key = _address_module(method_name)
    if module_key is None:
        return False
    if getattr(user, "access_mode", "") == "DEMO" and module_key not in DEMO_COMMAND_MODULES:
        return False
    return can_access(user, module_key, action_for_operation(method_name))


def modules_for_user(user) -> frozenset[str]:
    """Retorna módulos visíveis na navegação."""
    if getattr(user, "is_superuser", False) or role_name(user) == ADMIN:
        return frozenset({"*"})
    return frozenset(module.key for module in MODULES if can_access(user, module.key, VIEW))


def can_configure_student_diary(user) -> bool:
    """Restringe configuração estrutural da Agenda à coordenação e administração."""
    return role_name(user) != TEACHER and can_access(user, "student_diary", EDIT)


def can_edit_student_diary(user) -> bool:
    """Indica se o usuário pode preencher a Agenda no próprio escopo."""
    return can_access(user, "student_diary", EDIT)


def _address_module(method_name: str) -> str:
    """Faz endereços herdarem a capacidade da entidade proprietária."""
    for entity, module in (
        ("teacher", "teachers"),
        ("guardian", "guardians"),
        ("student", "students"),
        ("business_unit", "__admin__"),
        ("school", "__admin__"),
    ):
        if entity in method_name:
            return module
    return "students"


__all__ = [
    "CREATE",
    "DEACTIVATE",
    "EDIT",
    "GUARDIAN_VIEW_NAMES",
    "PUBLIC_VIEW_NAMES",
    "SELF_SERVICE_VIEW_NAMES",
    "VIEW",
    "access_policy",
    "can_access",
    "can_access_module",
    "can_configure_student_diary",
    "can_edit_student_diary",
    "can_execute_service",
    "has_unrestricted_tenant_access",
    "modules_for_user",
    "role_name",
    "resolve_view_access",
]
