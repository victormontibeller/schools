"""Testes das views do dashboard."""

import pytest
from django.test import override_settings
from django.urls import reverse

from core.models import Role


@pytest.mark.django_db
class TestDashboardViews:
    def test_school_dashboard_redirects_to_canonical_home(self, client, user):
        client.force_login(user)
        response = client.get(reverse("school_dashboard"))
        assert response.status_code == 302
        assert response.url == reverse("dashboard")

    def test_school_dashboard_partial(self, client, user):
        client.force_login(user)
        response = client.get(reverse("school_dashboard_partial"))
        assert response.status_code == 200

    def test_executive_requires_staff(self, client, user):
        client.force_login(user)
        response = client.get(reverse("executive_dashboard"))
        assert response.status_code == 302  # redirect to admin login

    def test_home_dashboard_renders_teacher_shortcuts_and_operational_widgets(self, client, user):
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
        assert "Minhas disciplinas" in content
        assert "Lançar frequência" in content
        assert "Atenção necessária" in content
        assert "Alunos ativos" in content
        assert "Resumo da escola" in content
        assert "Frequência da semana" in content
        assert "Comunicados recentes" in content
        assert "Módulos em foco" not in content
        assert "Todos os módulos" not in content

    @pytest.mark.parametrize(
        ("role_name", "expected_actions"),
        [
            (Role.Name.ADMIN, ["Novo aluno", "Novo professor", "Nova turma", "Usuários"]),
            (
                Role.Name.COORDINATOR,
                ["Novo aluno", "Novo professor", "Nova turma", "Calendário"],
            ),
        ],
    )
    def test_home_dashboard_renders_actions_for_operational_roles(
        self, client, user, role_name, expected_actions
    ):
        role, _ = Role.objects.get_or_create(
            name=role_name,
            defaults={"created_by": user, "updated_by": user},
        )
        user.role = role
        user.save(update_fields=["role"])
        client.force_login(user)

        response = client.get(reverse("dashboard"))

        content = response.content.decode()
        assert response.status_code == 200
        for action in expected_actions:
            assert action in content
        assert content.count('id="dashboard-widgets"') == 1

    def test_home_dashboard_renders_empty_states(self, client, user):
        client.force_login(user)

        response = client.get(reverse("dashboard"))

        content = response.content.decode()
        assert response.status_code == 200
        assert "Nenhuma pendência prioritária" in content
        assert "Nenhum evento próximo" in content

    @override_settings(ALLOWED_HOSTS=["platform.localhost"])
    def test_school_dashboard_redirects_platform_operator(self, client, user):
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        client.force_login(user)

        response = client.get(reverse("school_dashboard"), HTTP_HOST="platform.localhost")

        assert response.status_code == 302
        assert response.url == reverse("platform_dashboard")
