"""Views dos dashboards — escolar e executivo."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from dashboard.services import DashboardService


@login_required
def school_dashboard_partial(request: HttpRequest) -> HttpResponse:
    """Partial HTMX para atualizacao assincrona do dashboard escolar."""
    from core.tenant_routing import is_platform_request

    if is_platform_request(request):
        return redirect("platform_dashboard")
    from core.permissions import VIEW, can_access

    data = DashboardService(user=request.user).get_school_dashboard_data()
    diary_kpis = data.get("diary_kpis") or {}
    can_view_financial = can_access(request.user, "finance_overview", VIEW)
    can_view_revenue = can_access(request.user, "finance_revenue_reports", VIEW)
    can_view_overdue = can_access(request.user, "finance_overdue_reports", VIEW)
    return render(
        request,
        "dashboard/partials/operational_widgets.html",
        {
            "data": data,
            "can_view_financial": can_view_financial,
            "can_view_revenue": can_view_revenue,
            "can_view_overdue": can_view_overdue,
            "has_visible_attention": bool(
                data["students_at_risk"]
                or data["pending_activities"]
                or diary_kpis.get("pending_review")
                or diary_kpis.get("changes_requested")
                or (can_view_overdue and data["financial_kpis"]["total_vencido"])
            ),
        },
    )


@staff_member_required
def executive_dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard executivo — visao agregada de todos os tenants (admin only)."""
    from core.tenant_routing import is_platform_request

    if is_platform_request(request):
        return redirect("platform_dashboard")
    data = DashboardService(user=request.user).get_executive_dashboard_data()
    return render(request, "dashboard/executive.html", {"data": data})
