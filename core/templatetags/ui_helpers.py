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


@register.simple_tag(takes_context=True)
def can_access_action(context, module_key: str, action: str) -> bool:
    """Expõe a política central para ocultar controles sem duplicar regras."""
    from core.permissions import can_access

    return can_access(context["request"].user, module_key, action)


@register.simple_tag(takes_context=True)
def can_access_url(context, url_name: str | None) -> bool:
    """Resolve a capacidade declarada por uma rota sem argumentos."""
    if not url_name:
        return False
    from django.urls import NoReverseMatch, resolve, reverse

    from core.permissions import can_access, resolve_view_access

    try:
        match = resolve(reverse(url_name))
    except NoReverseMatch:
        return False
    module_key, action = resolve_view_access(match.func, match.url_name or "", "GET", {})
    return bool(module_key and can_access(context["request"].user, module_key, action))


@register.simple_tag(takes_context=True)
def can_access_entity_action(context, entity_type: str, action: str) -> bool:
    """Faz controles de endereço herdarem o módulo de sua entidade."""
    from core.permissions import can_access

    module_key = {
        "teacher": "teachers",
        "guardian": "guardians",
        "student": "students",
        "school": "__admin__",
        "business_unit": "__admin__",
    }.get(entity_type)
    if module_key == "__admin__":
        user = context["request"].user
        role = getattr(user, "role", None)
        return bool(getattr(user, "is_superuser", False) or getattr(role, "name", "") == "ADMIN")
    return bool(module_key and can_access(context["request"].user, module_key, action))
