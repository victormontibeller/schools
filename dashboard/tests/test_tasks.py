"""Testes das tasks tenant-aware de dashboard."""

from unittest.mock import patch

import pytest

from base import context
from dashboard.tasks import (
    refresh_all_school_dashboards,
    update_executive_dashboard_cache,
    update_school_dashboard_cache,
)


def test_update_school_dashboard_activates_received_schema():
    active_tenants: list[str] = []

    with patch(
        "dashboard.services.DashboardService.get_school_dashboard_data",
        side_effect=lambda: active_tenants.append(context.current_tenant.get()),
    ) as refresh:
        update_school_dashboard_cache.run("demo")

    assert active_tenants == ["demo"]
    assert context.current_tenant.get() == "public"
    refresh.assert_called_once_with()


@pytest.mark.django_db
def test_refresh_all_dashboards_dispatches_each_active_tenant(user):
    from tenancy.models import School

    School.objects.create(schema_name="tenant_a", name="A", created_by=user, updated_by=user)
    School.objects.create(schema_name="tenant_b", name="B", created_by=user, updated_by=user)
    with patch("dashboard.tasks.update_school_dashboard_cache.delay") as delay:
        refresh_all_school_dashboards.run()
    assert {call.args[0] for call in delay.call_args_list} == {"tenant_a", "tenant_b"}


def test_update_executive_dashboard_uses_public_aggregation():
    with patch("dashboard.services.DashboardService.get_executive_dashboard_data") as refresh:
        update_executive_dashboard_cache.run()
    refresh.assert_called_once_with()
