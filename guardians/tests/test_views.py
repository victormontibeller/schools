"""Testes das views de listagem de responsáveis."""

from urllib.parse import urlparse

import pytest
from django.conf import settings
from playwright.sync_api import Page, expect

from guardians.services import GuardianService


@pytest.fixture()
def force_login_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture()
def guardian(user):
    return GuardianService(user=user).create_guardian(
        {
            "first_name": "Carla",
            "last_name": "Listado",
            "email": "guardian-view@example.com",
            "birth_date": "1980-01-01",
            "gender": "F",
            "nationality": "Brasileira",
            "cpf": "529.982.247-25",
            "rg_number": "1234567",
            "rg_issuer": "SSP",
            "rg_state": "SP",
            "phone": "1133334444",
            "phone_whatsapp": "11999991111",
            "phone_mobile": "11988882222",
        }
    )


@pytest.mark.django_db
def test_guardians_list_renders(force_login_client, guardian):
    response = force_login_client.get("/guardians/?q=Carla&sort=name")

    assert response.status_code == 200
    assert b"Carla" in response.content


@pytest.mark.django_db
def test_guardian_detail_renders(force_login_client, guardian):
    response = force_login_client.get(f"/guardians/{guardian.pk}/")

    assert response.status_code == 200
    assert b"sm-profile-hero" in response.content
    assert b"avatar-text" in response.content
    assert guardian.full_name.encode() in response.content
    assert guardian.email.encode() in response.content
    assert b'hx-boost="true"' in response.content
    assert b'hx-target="#app-main"' in response.content
    assert b'hx-select="#app-main"' in response.content


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_guardian_edit_navigation_preserves_global_shell(
    page: Page,
    force_login_client,
    guardian,
    live_server,
) -> None:
    cookie = force_login_client.cookies[settings.SESSION_COOKIE_NAME]
    hostname = urlparse(live_server.url).hostname
    assert hostname is not None
    page.context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": cookie.value,
                "domain": hostname,
                "path": "/",
                "sameSite": "Lax",
            }
        ]
    )
    page.goto(f"{live_server.url}/guardians/{guardian.pk}/")

    navigation = page.locator("#school-navigation")
    edit_link = page.locator("#guardian-information-card").get_by_role("link", name="Editar")
    expect(edit_link).to_have_attribute("hx-boost", "true")
    navigation.evaluate("element => { element.dataset.persistenceMarker = 'preserved'; }")

    edit_link.click()

    expect(page).to_have_url(f"{live_server.url}/guardians/{guardian.pk}/editar/")
    expect(page.get_by_role("heading", name="Editar Responsável")).to_be_visible()
    expect(navigation).to_have_attribute("data-persistence-marker", "preserved")

    cancel_link = page.get_by_role("link", name="Cancelar")
    expect(cancel_link).to_have_attribute("hx-boost", "true")
    cancel_link.click()

    expect(page).to_have_url(f"{live_server.url}/guardians/")
    expect(
        page.locator(".sm-page-header").get_by_role("heading", name="Responsáveis", exact=True)
    ).to_be_visible()
    expect(navigation).to_have_attribute("data-persistence-marker", "preserved")


@pytest.mark.django_db
def test_guardian_edit_renders_with_links(force_login_client, guardian):
    response = force_login_client.get(
        f"/guardians/{guardian.pk}/editar/",
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Alunos vinculados" in response.content
    assert b'name="email"' in response.content
    assert b"disabled" in response.content
    assert b"sm-profile-avatar-input" in response.content
    assert guardian.full_name.encode() in response.content
    assert guardian.email.encode() in response.content
    assert b"btn btn-sm btn-outline-secondary" in response.content
    assert b"btn btn-sm btn-primary" in response.content
    assert b'hx-boost="true"' in response.content
    assert b'hx-target="#app-main"' in response.content
    assert b'hx-select="#app-main"' in response.content


@pytest.mark.django_db
def test_guardian_post_updates(force_login_client, guardian):
    response = force_login_client.post(
        f"/guardians/{guardian.pk}/editar/",
        {
            "first_name": "Carla",
            "last_name": "Atualizada",
            "email": "guardian-view@example.com",
            "relationship_type": "PAI",
            "birth_date": "1985-03-10",
            "gender": "F",
            "nationality": "Brasileiro",
            "cpf": "390.533.447-05",
            "rg_number": "7654321",
            "rg_issuer": "SSP",
            "rg_state": "SP",
            "phone": "(11) 3333-4444",
            "phone_whatsapp": "(11) 99999-1111",
            "phone_mobile": "(11) 98888-2222",
            "version": guardian.version,
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 302
    guardian.refresh_from_db()
    assert guardian.last_name == "Atualizada"


@pytest.mark.django_db
def test_guardian_edit_ignores_submitted_email_change(force_login_client, guardian):
    original_email = guardian.email

    response = force_login_client.post(
        f"/guardians/{guardian.pk}/editar/",
        {
            "first_name": guardian.first_name,
            "last_name": guardian.last_name,
            "email": "alterado@example.com",
            "birth_date": guardian.birth_date,
            "gender": guardian.gender,
            "cpf": guardian.cpf,
            "rg_number": guardian.rg_number,
            "phone_mobile": guardian.phone_mobile,
            "version": guardian.version,
        },
    )

    assert response.status_code == 302
    guardian.refresh_from_db()
    assert guardian.email == original_email
