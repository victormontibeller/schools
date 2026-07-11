"""Testes da gestão de escolas e operadores no painel público."""

import pytest
from django.test import override_settings
from django.urls import reverse

from base.exceptions import BusinessRuleViolationError, ValidationError


@pytest.fixture()
def platform_admin(user):
    """Transforma a fixture base em superusuário da plataforma."""
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    return user


@pytest.mark.django_db
def test_create_platform_school_provisions_primary_domain(platform_admin):
    from tenancy.models import Domain
    from tenancy.services import PlatformSchoolService

    school = PlatformSchoolService(user=platform_admin).create_platform_school(
        {
            "name": "Colégio Horizonte",
            "schema_name": "colegio_horizonte",
            "domain": "horizonte.localhost",
            "email": "contato@horizonte.test",
        }
    )

    assert school.schema_name == "colegio_horizonte"
    assert Domain.objects.filter(domain="horizonte.localhost", tenant=school).exists()


@pytest.mark.django_db
def test_create_platform_school_rejects_duplicate_schema(platform_admin):
    from tenancy.models import School
    from tenancy.services import PlatformSchoolService

    School.objects.create(
        schema_name="colegio_existente",
        name="Colégio Existente",
        created_by=platform_admin,
        updated_by=platform_admin,
    )
    with pytest.raises(ValidationError):
        PlatformSchoolService(user=platform_admin).create_platform_school(
            {
                "name": "Outro Colégio",
                "schema_name": "colegio_existente",
                "domain": "outro.localhost",
            }
        )


@pytest.mark.django_db
def test_update_platform_user_prevents_self_lockout(platform_admin):
    from accounts.services import AccountService

    with pytest.raises(BusinessRuleViolationError):
        AccountService(user=platform_admin).update_platform_user(
            platform_admin.pk,
            {
                "first_name": platform_admin.first_name,
                "last_name": platform_admin.last_name,
                "is_active": False,
                "is_superuser": False,
            },
        )


@pytest.mark.django_db
def test_create_platform_user_creates_staff_operator(platform_admin):
    from accounts.services import AccountService

    operator = AccountService(user=platform_admin).create_platform_user(
        {
            "first_name": "Operador",
            "last_name": "Suporte",
            "email": "operador@platform.test",
            "password": "Senha123",
            "is_superuser": False,
        }
    )

    assert operator.is_staff is True
    assert operator.is_superuser is False
    assert operator.check_password("Senha123")


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["platform.localhost"])
def test_platform_school_create_view_provisions_school(client, platform_admin):
    from tenancy.models import Domain, School

    client.force_login(platform_admin)
    response = client.post(
        reverse("platform_school_create"),
        {
            "name": "Escola Nova",
            "schema_name": "escola_nova",
            "domain": "escola-nova.localhost",
            "email": "",
            "phone": "",
        },
        HTTP_HOST="platform.localhost",
    )

    assert response.status_code == 302
    school = School.objects.get(schema_name="escola_nova")
    assert Domain.objects.filter(domain="escola-nova.localhost", tenant=school).exists()


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["platform.localhost"])
def test_platform_user_create_view_creates_operator(client, platform_admin):
    from core.models import CustomUser

    client.force_login(platform_admin)
    response = client.post(
        reverse("platform_user_create"),
        {
            "first_name": "Novo",
            "last_name": "Operador",
            "email": "novo-operador@platform.test",
            "password": "Senha123",
            "confirm_password": "Senha123",
        },
        HTTP_HOST="platform.localhost",
    )

    assert response.status_code == 302
    assert CustomUser.objects.filter(email="novo-operador@platform.test", is_staff=True).exists()
