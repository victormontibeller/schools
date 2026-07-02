"""Filtros auxiliares para renderização de formulários compartilhados."""

from django import template

register = template.Library()


@register.filter
def widget_type(widget) -> str:
    """Retorna o nome da classe do widget (ex.: 'TextareaInput')."""
    return widget.__class__.__name__


@register.filter
def form_widget(bound_field):
    """Renderiza um BoundField com a classe Bootstrap adequada ao widget."""
    widget = bound_field.field.widget
    input_type = getattr(widget, "input_type", "")
    widget_name = widget.__class__.__name__
    attrs = dict(widget.attrs)

    if input_type == "hidden":
        return bound_field.as_widget()
    if input_type in {"checkbox", "radio"}:
        css_class = "form-check-input"
    elif widget_name in {"Select", "SelectMultiple"}:
        css_class = "form-select"
    else:
        css_class = "form-control"

    existing_classes = attrs.get("class", "").split()
    attrs["class"] = " ".join(dict.fromkeys([*existing_classes, css_class]))
    return bound_field.as_widget(attrs=attrs)
