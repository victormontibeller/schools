"""Filtros de template auxiliares para o calendário."""

from django import template

register = template.Library()


@register.filter
def get(mapping, key):
    """Retorna mapping[key] ou None (suporta dict-access em templates)."""
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return mapping[key]
