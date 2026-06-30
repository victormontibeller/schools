"""Views dos dashboards — escolar e executivo."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from dashboard.services import DashboardService


@login_required
def school_dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard escolar com KPIs, frequencia, atividades e eventos."""
    data = DashboardService(user=request.user).get_school_dashboard_data()
    return render(request, "dashboard/school.html", {"data": data})


@login_required
def school_dashboard_partial(request: HttpRequest) -> HttpResponse:
    """Partial HTMX para atualizacao assincrona do dashboard escolar."""
    data = DashboardService(user=request.user).get_school_dashboard_data()
    return render(request, "dashboard/partials/school_widgets.html", {"data": data})


@staff_member_required
def executive_dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard executivo — visao agregada de todos os tenants (admin only)."""
    data = DashboardService(user=request.user).get_executive_dashboard_data()
    return render(request, "dashboard/executive.html", {"data": data})
