"""Testes de integracao das views de enderecos."""

import pytest

from base.exceptions import ValidationError
from tenancy.models import School


@pytest.fixture()
def force_login_client(client, user, db):
    client.force_login(user)
    return client


@pytest.fixture()
def school(user):
    return School.objects.create(
        schema_name="testaddrviews",
        name="Escola Endereco Views",
        created_by=user,
        updated_by=user,
    )


@pytest.fixture()
def address_for_school(user, school):
    from addresses.models import Address, SchoolAddress

    addr = Address.objects.create(
        street="Rua Teste",
        number="123",
        district="Centro",
        postal_code="01001000",
        city="Sao Paulo",
        state="SP",
        created_by=user,
        updated_by=user,
    )
    SchoolAddress.objects.create(
        school=school,
        address=addr,
        is_primary=True,
        created_by=user,
        updated_by=user,
    )
    return addr


@pytest.mark.django_db
class TestAddressViews:
    def test_address_create_for_entity_get_renders_form(self, force_login_client, school):
        resp = force_login_client.get(f"/addresses/create/school/{school.pk}/")
        assert resp.status_code == 200
        assert b"form" in resp.content.lower()

    def test_address_create_for_entity_post_creates_and_redirects(self, force_login_client, school):
        data = {
            "recipient": "Secretaria",
            "street": "Av Brasil",
            "number": "1000",
            "complement": "Bloco A",
            "district": "Centro",
            "postal_code": "01001000",
            "city": "São Paulo",
            "state": "SP",
        }
        resp = force_login_client.post(f"/addresses/create/school/{school.pk}/", data)
        assert resp.status_code == 302

    def test_address_edit_get_renders_form(self, force_login_client, address_for_school):
        resp = force_login_client.get(f"/addresses/{address_for_school.pk}/edit/")
        assert resp.status_code == 200
        assert b"form" in resp.content.lower()

    def test_address_edit_post_updates_and_redirects(self, force_login_client, address_for_school):
        data = {
            "recipient": "Coordenação",
            "street": "Rua Nova",
            "number": "500",
            "complement": "Sala 2",
            "district": "Vila Nova",
            "postal_code": "02002000",
            "city": "São Paulo",
            "state": "SP",
        }
        resp = force_login_client.post(f"/addresses/{address_for_school.pk}/edit/", data)
        assert resp.status_code == 302
        address_for_school.refresh_from_db()
        assert address_for_school.street == "Rua Nova"

    def test_address_create_htmx_returns_inline_card(self, force_login_client, school):
        response = force_login_client.get(
            f"/addresses/create/school/{school.pk}/",
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert b'id="addresses-card"' in response.content
        assert b"Novo Endereco" in response.content

    def test_address_edit_htmx_returns_inline_card(self, force_login_client, address_for_school):
        response = force_login_client.get(
            f"/addresses/{address_for_school.pk}/edit/",
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert b'id="addresses-card"' in response.content
        assert b"Editar Endereco" in response.content

    def test_address_create_invalid_entity_type_redirects(self, force_login_client, school):
        resp = force_login_client.get(f"/addresses/create/invalid/{school.pk}/")
        assert resp.status_code == 302

    def test_address_deactivate_post_redirects(self, force_login_client, address_for_school):
        resp = force_login_client.post(
            f"/addresses/{address_for_school.pk}/deactivate/",
            HTTP_REFERER="/app/empresa/",
        )
        assert resp.status_code == 302

    def test_address_create_post_invalid_rerenders(self, force_login_client, school):
        resp = force_login_client.post(
            f"/addresses/create/school/{school.pk}/",
            data={"street": ""},
        )
        assert resp.status_code == 200

    def test_address_city_options_returns_only_selected_state_cities(self, force_login_client):
        response = force_login_client.get("/addresses/city-options/?state=SP&city=Campinas")

        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="city-field-container"' in content
        assert "Campinas" in content
        assert "São Paulo" in content
        assert "Niterói" not in content

    def test_address_postal_code_lookup_prefills_form_fields(
        self,
        force_login_client,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "addresses.services.AddressService.lookup_postal_code",
            lambda self, postal_code: {
                "postal_code": "01001-000",
                "street": "Praça da Sé",
                "district": "Sé",
                "complement": "lado ímpar",
                "state": "SP",
                "city": "São Paulo",
            },
        )

        response = force_login_client.get(
            "/addresses/postal-code-lookup/",
            {
                "postal_code": "01001000",
                "recipient": "Secretaria",
                "number": "100",
            },
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="address-form-fields"' in content
        assert 'value="Praça da Sé"' in content
        assert 'value="Sé"' in content
        assert 'value="01001-000"' in content
        assert 'value="100"' in content
        assert 'value="São Paulo"' in content

    def test_address_postal_code_lookup_renders_field_error_when_service_fails(
        self,
        force_login_client,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "addresses.services.AddressService.lookup_postal_code",
            lambda self, postal_code: (_ for _ in ()).throw(
                ValidationError(errors={"postal_code": ["CEP nao encontrado."]})
            ),
        )

        response = force_login_client.get(
            "/addresses/postal-code-lookup/",
            {"postal_code": "99999999"},
        )

        assert response.status_code == 200
        assert b"CEP nao encontrado." in response.content
