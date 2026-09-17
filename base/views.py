"""Orquestração HTTP compartilhada para componentes com fallback de página."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def render_component_form(
    request: HttpRequest, template: str, context: dict, *, title: str
) -> HttpResponse:
    """Renderiza o mesmo formulário como fragmento HTMX ou página canônica."""
    if request.headers.get("HX-Request"):
        return render(request, template, context)
    return render(
        request,
        "person_information_page.html",
        {
            **context,
            "component_template": template,
            "title": title,
        },
    )
