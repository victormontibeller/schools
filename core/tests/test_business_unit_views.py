"""Testes das views de empresas (unidades de negocio)."""

import pytest


def _unit_payload(**overrides):
    data = {
        "name": "Unidade Nova",
        "legal_name": "Unidade Nova Ltda.",
        "trade_name": "Unidade Nova",
        "cnpj": "44555666000181",
        "state_registration": "110042490114",
        "municipal_registration": "123456",
        "phone": "1133334444",
        "email": "unidade@example.com",
        "academic_year_start": "2026-02-01",
        "academic_year_end": "2026-12-15",
        "contact_full_name": "Maria Silva",
        "contact_role": "Diretora",
        "contact_phone": "11999990000",
        "contact_email": "maria@example.com",
    }
    data.update(overrides)
    return data


@pytest.fixture()
def force_login_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture()
def business_unit(user):
    from core.models import BusinessUnit

    return BusinessUnit.objects.create(
        name="Unidade Sul",
        cnpj="33444555000181",
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
def test_business_unit_list_renders(force_login_client, business_unit):
    response = force_login_client.get("/app/empresas/")

    assert response.status_code == 200
    assert business_unit.name.encode() in response.content
    assert f"/app/empresas/{business_unit.pk}/".encode() in response.content


@pytest.mark.django_db
def test_business_unit_detail_renders(force_login_client, business_unit):
    response = force_login_client.get(f"/app/empresas/{business_unit.pk}/")

    assert response.status_code == 200
    assert business_unit.name.encode() in response.content
    assert f"/app/empresas/{business_unit.pk}/editar/".encode() in response.content


@pytest.mark.django_db
def test_business_unit_create_creates_and_redirects(force_login_client):
    response = force_login_client.post(
        "/app/empresas/nova/",
        _unit_payload(),
    )

    assert response.status_code == 302
    assert "/app/empresas/" in response["Location"]


@pytest.mark.django_db
def test_business_unit_edit_updates_and_redirects(force_login_client, business_unit):
    response = force_login_client.post(
        f"/app/empresas/{business_unit.pk}/editar/",
        _unit_payload(name="Unidade Sul Atualizada", cnpj=business_unit.cnpj),
    )

    assert response.status_code == 302
    business_unit.refresh_from_db()
    assert business_unit.name == "Unidade Sul Atualizada"


@pytest.mark.django_db
def test_business_unit_edit_returns_component_for_htmx(force_login_client, business_unit):
    response = force_login_client.get(
        f"/app/empresas/{business_unit.pk}/editar/",
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Cancelar" in response.content
    assert b"<html" not in response.content
