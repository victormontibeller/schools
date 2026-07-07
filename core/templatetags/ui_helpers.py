"""Helpers de template para UI compartilhada."""

from django import template

register = template.Library()


@register.filter
def user_role_label(user) -> str:
    """Retorna o rótulo amigável do perfil exibido no cabeçalho."""
    if getattr(user, "role_id", None) and getattr(user, "role", None):
        return str(user.role)
    if hasattr(user, "teacher_profile"):
        return "Professor"
    if hasattr(user, "guardian_profile"):
        return "Responsável"
    if getattr(user, "is_staff", False):
        return "Administrador"
    return "Coordenador" if getattr(user, "is_authenticated", False) else "Usuário"
