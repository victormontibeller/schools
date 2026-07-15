"""Montagem da navegação autenticada da escola."""

from typing import Any

from core.access_catalog import ADMIN, GUARDIAN, TEACHER
from core.navigation_catalog import GUARDIAN_NAVIGATION, STAFF_NAVIGATION, TEACHER_NAVIGATION
from core.permissions import can_access, role_name


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
    """Usa somente a política central; a taxonomia limita papéis com escopo."""
    if item["module"] == "__admin__":
        return getattr(user, "is_superuser", False) or role_name(user) == ADMIN
    return can_access(user, item["module"], "view")


def build_school_navigation(user, view_name: str) -> dict[str, Any]:
    """Retorna links e grupos autorizados com o estado da rota corrente."""
    direct_links = []
    if can_access(user, "dashboard", "view"):
        direct_links.append(
            {
                "label": "Visão geral",
                "icon": "feather-airplay",
                "url_name": "dashboard",
                "active": view_name == "dashboard",
            }
        )
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
