"""Testes de integracao das views de enderecos."""

import pytest

from core.models import School


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
            "street": "Av Brasil",
            "number": "1000",
            "district": "Centro",
            "postal_code": "01001000",
            "city": "Sao Paulo",
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
            "street": "Rua Nova",
            "number": "500",
            "district": "Vila Nova",
            "postal_code": "02002000",
            "city": "Sao Paulo",
            "state": "SP",
        }
        resp = force_login_client.post(f"/addresses/{address_for_school.pk}/edit/", data)
        assert resp.status_code == 302
        address_for_school.refresh_from_db()
        assert address_for_school.street == "Rua Nova"

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
