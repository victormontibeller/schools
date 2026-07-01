"""Filtros auxiliares para renderização de formulários compartilhados."""

from django import template

register = template.Library()


@register.filter
def widget_type(widget) -> str:
    """Retorna o nome da classe do widget (ex.: 'TextareaInput')."""
    return widget.__class__.__name__
