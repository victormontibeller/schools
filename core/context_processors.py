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
