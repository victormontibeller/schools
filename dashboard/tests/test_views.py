"""Testes das views do dashboard."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestDashboardViews:
    def test_school_dashboard(self, client, user):
        client.force_login(user)
        response = client.get(reverse("school_dashboard"))
        assert response.status_code == 200
        assert "Dashboard Escolar" in response.content.decode()

    def test_school_dashboard_partial(self, client, user):
        client.force_login(user)
        response = client.get(reverse("school_dashboard_partial"))
        assert response.status_code == 200

    def test_executive_requires_staff(self, client, user):
        client.force_login(user)
        response = client.get(reverse("executive_dashboard"))
        assert response.status_code == 302  # redirect to admin login
