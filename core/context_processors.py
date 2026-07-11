"""Context processors compartilhados do projeto."""

from __future__ import annotations


def current_school(request):
    """Disponibiliza a escola atual para o layout autenticado."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"current_school": None}

    from core.selectors import SchoolSelector

    try:
        school = SchoolSelector().get_current_school()
    except Exception:
        school = None
    return {"current_school": school}


def support_access(request):
    """Expõe o estado de impersonação para o banner global."""
    session = getattr(request, "session", {})
    return {
        "support_access_active": bool(session.get("support_grant_id")),
        "support_grant_id": session.get("support_grant_id", ""),
        "support_expires_at": session.get("support_expires_at", ""),
    }


def accessible_modules(request):
    """Disponibiliza módulos autorizados para a navegação."""
    from core.permissions import modules_for_user
    from core.tenant_routing import is_platform_request

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"accessible_modules": frozenset(), "is_platform_schema": False}
    is_platform = is_platform_request(request)
    return {
        "accessible_modules": (frozenset() if is_platform else modules_for_user(request.user)),
        "is_platform_schema": is_platform,
    }


def school_navigation(request):
    """Disponibiliza a navegacao escolar autorizada e o grupo da rota atual."""
    from core.navigation import build_school_navigation
    from core.tenant_routing import is_platform_request

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or is_platform_request(request):
        return {
            "school_navigation": {
                "direct_links": [],
                "groups": [],
                "active_group_id": "",
                "active_url_name": "",
            }
        }
    resolver_match = getattr(request, "resolver_match", None)
    view_name = getattr(resolver_match, "url_name", "") or ""
    return {"school_navigation": build_school_navigation(user, view_name)}
