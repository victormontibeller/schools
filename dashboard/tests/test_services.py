"""Testes do DashboardService com cache."""

from unittest.mock import patch

import pytest

from dashboard.services import CACHE_TTL, DashboardService


@pytest.mark.django_db
class TestDashboardService:
    def test_get_school_dashboard(self, user):
        data = DashboardService(user=user).get_school_dashboard_data()
        assert "total_students" in data
        assert "total_teachers" in data
        assert "total_classes" in data
        assert "financial_kpis" in data
        assert data["total_students"] == 0

    def test_financial_kpis_receive_guardian_for_object_scope(self, django_user_model, user):
        from core.models import Role, RoleModuleAccess

        guardian_role = Role.objects.get(name=Role.Name.GUARDIAN)
        guardian = django_user_model.objects.create_user(
            email="guardian-dashboard@test.com",
            password="Senha123",
            role=guardian_role,
        )
        RoleModuleAccess.objects.filter(role=guardian_role, module_key="finance_overview").update(
            can_view=True
        )
        expected = {
            "total_aberto": 0,
            "total_vencido": 0,
            "recebido_mes": 0,
            "partial_count": 0,
            "pending_reconciliation": 0,
            "reminder_failures": 0,
        }

        with patch(
            "dashboard.selectors.DashboardSelector.get_financial_kpis",
            return_value=expected,
        ) as get_financial_kpis:
            data = DashboardService(user=guardian).get_school_dashboard_data()

        assert data["financial_kpis"] == expected
        get_financial_kpis.assert_called_once_with(guardian)

    def test_get_executive_dashboard(self, user):
        data = DashboardService(user=user).get_executive_dashboard_data()
        assert "total_tenants" in data
        assert "platform_users" in data
        assert "platform_growth" in data

    def test_cache_returns_same_data(self, user):
        svc = DashboardService(user=user)
        d1 = svc.get_school_dashboard_data()
        d2 = svc.get_school_dashboard_data()
        assert d1 == d2

    def test_invalidate_cache(self, user):
        svc = DashboardService(user=user)
        svc.get_school_dashboard_data()
        svc.invalidate_cache()
        # Apos invalidar, nova chamada busca do banco.
        d2 = svc.get_school_dashboard_data()
        assert d2 is not None

    def test_cache_key_format(self):
        key = DashboardService._cache_key("test", "123")
        assert key == "tenant:public:dashboard:test:123"
        key2 = DashboardService._cache_key("test")
        assert key2 == "tenant:public:dashboard:test"

    def test_cache_ttls_defined(self):
        assert "total_students" in CACHE_TTL
        assert "today_attendance" in CACHE_TTL
        assert CACHE_TTL["today_attendance"] < CACHE_TTL["total_students"]
