"""Orquestração HTTP da listagem de turmas e da matriz semanal."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from agenda.presentation import (
    as_of_from_request,
    is_component_htmx_request,
    matrix_context,
    matrix_url,
)
from agenda.selectors import ScheduleSelector
from base.listing import build_querystring, build_sorting, resolve_listing_state
from core.permissions import access_policy, role_name


@login_required
@access_policy("schedule", "view")
def schedule_classes_list(request: HttpRequest) -> HttpResponse:
    """Lista as turmas disponíveis para abertura da matriz semanal."""
    state = resolve_listing_state(
        request,
        scope="schedule_classes_list",
        allowed_sorts={
            "name",
            "-name",
            "academic_year",
            "-academic_year",
            "grade",
            "-grade",
            "shift",
            "-shift",
        },
        default_sort="-academic_year",
    )
    search, sort = state["q"], state["sort"]
    result = ScheduleSelector().list_classes_for_matrix(
        user_id=request.user.pk,
        role_name=role_name(request.user),
        search=search,
        order_by=sort,
        page=state["page"],
    )
    context = {
        "result": result,
        "q": search,
        "sort": sort,
        "sorting": build_sorting(
            current_sort=sort,
            search=search,
            sortable_fields=["name", "grade", "shift", "academic_year"],
        ),
        "list_query": build_querystring({"q": search, "sort": sort}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Grade Horária", "url": None},
        ],
    }
    template_name = (
        "agenda/partials/schedule_classes_table.html"
        if is_component_htmx_request(request)
        else "agenda/schedule_classes_list.html"
    )
    return render(request, template_name, context)


@login_required
@access_policy("schedule", "view")
def schedule_weekly(request: HttpRequest, class_id) -> HttpResponse:
    """Exibe a matriz de segunda a sexta na semana canônica solicitada."""
    as_of = as_of_from_request(request)
    if request.GET.get("as_of") != as_of.isoformat():
        canonical_url = matrix_url(class_id, as_of)
        if is_component_htmx_request(request):
            response = HttpResponse(status=204)
            response["HX-Redirect"] = canonical_url
            return response
        return redirect(canonical_url)
    context = matrix_context(request.user, class_id, as_of)
    template_name = (
        "agenda/partials/schedule_matrix_workspace.html"
        if is_component_htmx_request(request)
        else "agenda/schedule_weekly.html"
    )
    return render(request, template_name, context)
