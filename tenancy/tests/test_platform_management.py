"""Testes da gestão de escolas e operadores no painel público."""

import pytest
from django.test import override_settings
from django.urls import reverse

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError


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
            "password": "Violeta824",
            "is_superuser": False,
        }
    )

    assert operator.is_staff is True
    assert operator.is_superuser is False
    assert operator.check_password("Violeta824")


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
            "password": "Violeta824",
            "confirm_password": "Violeta824",
        },
        HTTP_HOST="platform.localhost",
    )

    assert response.status_code == 302
    assert CustomUser.objects.filter(email="novo-operador@platform.test", is_staff=True).exists()


@pytest.mark.django_db
def test_update_platform_school_changes_catalog_and_primary_domain(platform_admin):
    from tenancy.models import Domain
    from tenancy.services import PlatformSchoolService

    school = PlatformSchoolService(user=platform_admin).create_platform_school(
        {
            "name": "Escola Original",
            "schema_name": "escola_original",
            "domain": "original.localhost",
        }
    )
    updated = PlatformSchoolService(user=platform_admin).update_platform_school(
        school.pk,
        {
            "name": "Escola Atualizada",
            "domain": "atualizada.localhost",
            "email": "contato@example.com",
            "is_active": False,
        },
    )

    assert updated.name == "Escola Atualizada"
    assert updated.is_active is False
    assert Domain.objects.get(tenant=school, is_primary=True).domain == "atualizada.localhost"


@pytest.mark.django_db
def test_update_platform_school_rejects_duplicates_and_missing(platform_admin):
    import uuid

    from tenancy.services import PlatformSchoolService

    first = PlatformSchoolService(user=platform_admin).create_platform_school(
        {"name": "Primeira", "schema_name": "primeira", "domain": "primeira.localhost"}
    )
    second = PlatformSchoolService(user=platform_admin).create_platform_school(
        {"name": "Segunda", "schema_name": "segunda", "domain": "segunda.localhost"}
    )
    with pytest.raises(ValidationError):
        PlatformSchoolService(user=platform_admin).update_platform_school(
            second.pk, {"name": first.name, "domain": "terceira.localhost"}
        )
    with pytest.raises(ObjectNotFoundError):
        PlatformSchoolService(user=platform_admin).update_platform_school(
            uuid.uuid4(), {"name": "Ausente", "domain": "ausente.localhost"}
        )


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["platform.localhost"])
def test_platform_school_list_and_edit_views(client, platform_admin):
    from tenancy.models import Domain, School

    school = School.objects.create(
        schema_name="painel",
        name="Escola Painel",
        created_by=platform_admin,
        updated_by=platform_admin,
    )
    Domain.objects.create(domain="painel.localhost", tenant=school, is_primary=True)
    client.force_login(platform_admin)

    list_url = reverse("platform_school_list")
    assert client.get(list_url, HTTP_HOST="platform.localhost").status_code == 200
    assert (
        client.get(list_url, HTTP_HOST="platform.localhost", HTTP_HX_REQUEST="true").status_code
        == 200
    )

    edit_url = reverse("platform_school_edit", args=[school.pk])
    assert client.get(edit_url, HTTP_HOST="platform.localhost").status_code == 200
    response = client.post(
        edit_url,
        {
            "name": "Escola Painel Atualizada",
            "domain": "painel-novo.localhost",
            "email": "",
            "phone": "",
            "is_active": "on",
        },
        HTTP_HOST="platform.localhost",
    )
    assert response.status_code == 302
    school.refresh_from_db()
    assert school.name == "Escola Painel Atualizada"
