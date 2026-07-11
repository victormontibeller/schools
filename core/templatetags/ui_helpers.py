"""Helpers de template para UI compartilhada."""

from django import template

register = template.Library()


@register.filter
def user_role_label(user) -> str:
    """Retorna o rótulo amigável do perfil exibido no cabeçalho."""
    if getattr(user, "role_id", None) and getattr(user, "role", None):
        return str(user.role)
    # Operadores do schema público não possuem tabelas de perfis escolares.
    # Verificar staff antes das relações reversas evita consultas a apps tenant-only.
    if getattr(user, "is_staff", False):
        if getattr(user, "is_superuser", False):
            return "Administrador da Plataforma"
        return "Administrador"
    if hasattr(user, "teacher_profile"):
        return "Professor"
    if hasattr(user, "guardian_profile"):
        return "Responsável"
    return "Coordenador" if getattr(user, "is_authenticated", False) else "Usuário"


@register.filter
def module_allowed(modules, app_label: str) -> bool:
    """Indica se um módulo deve aparecer na navegação."""
    return "*" in modules or app_label in modules
