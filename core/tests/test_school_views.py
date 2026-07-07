"""Testes de integracao das views da empresa."""

import pytest

from core.models import School


@pytest.fixture()
def force_login_client(client, user, db):
    client.force_login(user)
    return client


@pytest.fixture()
def school(user):
    return School.objects.create(
        schema_name="testschoolviews",
        name="Escola Teste Views",
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
class TestSchoolDetail:
    def test_get_renders_company_information(self, force_login_client, school):
        resp = force_login_client.get("/app/empresa/")
        assert resp.status_code == 200
        assert school.name.encode() in resp.content
        assert b"/app/empresa/editar/" in resp.content

    def test_get_no_school_redirects_to_dashboard(self, force_login_client):
        resp = force_login_client.get("/app/empresa/")
        assert resp.status_code == 302
        assert "/app/empresas/" in resp["Location"]


@pytest.mark.django_db
class TestSchoolEdit:
    def test_get_renders_form(self, force_login_client, school):
        resp = force_login_client.get("/app/empresa/editar/")
        assert resp.status_code == 200
        assert b"form" in resp.content.lower()

    def test_get_no_school_redirects_to_dashboard(self, force_login_client):
        resp = force_login_client.get("/app/empresa/editar/")
        assert resp.status_code == 302
        assert "/app/empresas/" in resp["Location"]

    def test_post_updates_and_redirects(self, force_login_client, school):
        resp = force_login_client.post(
            "/app/empresa/editar/",
            data={
                "name": "Escola Atualizada",
                "phone": "1133445566",
                "email": "novo@escola.com",
            },
        )
        assert resp.status_code == 302
        assert resp["Location"] == "/app/escola/"
        school.refresh_from_db()
        assert school.name == "Escola Atualizada"
        assert school.phone == "1133445566"

    def test_post_missing_name_rerenders_form(self, force_login_client, school):
        resp = force_login_client.post("/app/empresa/editar/", data={"name": ""})
        assert resp.status_code == 200

    def test_get_returns_component_for_htmx(self, force_login_client, school):
        resp = force_login_client.get(
            "/app/empresa/editar/",
            HTTP_HX_REQUEST="true",
        )

        assert resp.status_code == 200
        assert b"Cancelar" in resp.content
        assert b"<html" not in resp.content
