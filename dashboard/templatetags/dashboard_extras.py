"""Template tags auxiliares para o dashboard."""

from django import template

register = template.Library()


@register.filter
def default(value, fallback="—"):
    """Retorna fallback se value for None ou vazio."""
    if value is None or value == "":
        return fallback
    return value
