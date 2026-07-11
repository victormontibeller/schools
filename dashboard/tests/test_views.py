"""Testes das views do dashboard."""

import pytest
from django.test import override_settings
from django.urls import reverse

from core.models import Role


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

    def test_home_dashboard_renders_role_based_shortcuts(self, client, user):
        role, _ = Role.objects.get_or_create(
            name=Role.Name.TEACHER,
            defaults={"created_by": user, "updated_by": user},
        )
        user.role = role
        user.save(update_fields=["role"])
        client.force_login(user)

        response = client.get(reverse("dashboard"))

        content = response.content.decode()
        assert response.status_code == 200
        assert "rotina de rotina docente" in content.lower()
        assert "Minhas disciplinas" in content
        assert "Lançar frequência" in content
        assert "Módulos em foco" in content

    @override_settings(ALLOWED_HOSTS=["platform.localhost"])
    def test_school_dashboard_redirects_platform_operator(self, client, user):
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        client.force_login(user)

        response = client.get(reverse("school_dashboard"), HTTP_HOST="platform.localhost")

        assert response.status_code == 302
        assert response.url == reverse("platform_dashboard")
