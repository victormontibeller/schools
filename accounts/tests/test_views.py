"""Testes das views de consulta de usuários."""

import pytest
from django.urls import reverse

from core.models import CustomUser


@pytest.fixture()
def force_login_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture()
def listed_user(db):
    return CustomUser.objects.create_user(
        email="listed@example.com",
        password="Senha123",
        first_name="Usuario",
        last_name="Listado",
    )


@pytest.mark.django_db
def test_users_list_links_name_to_detail(force_login_client, listed_user):
    response = force_login_client.get("/users/")

    assert response.status_code == 200
    assert f"/users/{listed_user.pk}/".encode() in response.content


@pytest.mark.django_db
def test_user_detail_renders_person_information(force_login_client, listed_user):
    response = force_login_client.get(f"/users/{listed_user.pk}/")

    assert response.status_code == 200
    assert listed_user.get_full_name().encode() in response.content
    assert listed_user.email.encode() in response.content


@pytest.mark.django_db
def test_users_list_persists_search_and_sort_in_session(force_login_client, listed_user):
    response = force_login_client.get("/users/?q=Listado&sort=email")

    assert response.status_code == 200
    assert response.context["q"] == "Listado"
    assert response.context["sort"] == "email"
    assert force_login_client.session["listing_state"]["users_list"] == {
        "q": "Listado",
        "sort": "email",
    }


@pytest.mark.django_db
def test_users_list_restores_saved_state_when_query_is_omitted(force_login_client, listed_user):
    session = force_login_client.session
    session["listing_state"] = {"users_list": {"q": "Listado", "sort": "email"}}
    session.save()

    response = force_login_client.get("/users/")

    assert response.status_code == 200
    assert response.context["q"] == "Listado"
    assert response.context["sort"] == "email"


@pytest.mark.django_db
def test_user_edit_returns_component_for_htmx(force_login_client, listed_user):
    response = force_login_client.get(
        f"/users/{listed_user.pk}/editar/",
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Cancelar" in response.content
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_profile_redirects_to_authenticated_user_detail(force_login_client, user):
    response = force_login_client.get(reverse("profile"))

    assert response.status_code == 302
    assert response.url == reverse("user_detail", kwargs={"pk": user.pk})


@pytest.mark.django_db
def test_user_edit_updates_email_via_htmx(force_login_client, user):
    response = force_login_client.post(
        reverse("user_edit", kwargs={"pk": user.pk}),
        {
            "first_name": "Admin",
            "last_name": "Atualizado",
            "email": "ATUALIZADO@EXAMPLE.COM",
            "phone": "11999999999",
            "role": user.role_id,
            "is_active": "on",
        },
        HTTP_HX_REQUEST="true",
    )

    user.refresh_from_db()
    assert response.status_code == 200
    assert user.email == "atualizado@example.com"
    assert "Informações atualizadas com sucesso.".encode() in response.content


@pytest.mark.django_db
def test_user_edit_shows_duplicate_email_error_via_htmx(force_login_client, user):
    CustomUser.objects.create_user(
        email="existente@example.com",
        password="Senha123",
        is_active=False,
    )

    response = force_login_client.post(
        reverse("user_edit", kwargs={"pk": user.pk}),
        {
            "first_name": "Admin",
            "last_name": "Test",
            "email": "EXISTENTE@example.com",
            "phone": "11999999999",
            "role": user.role_id,
            "is_active": "on",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert "Este e-mail já está em uso.".encode() in response.content


@pytest.mark.django_db
def test_change_password_redirects_to_authenticated_user_detail(force_login_client, user):
    response = force_login_client.post(
        reverse("change_password"),
        {
            "current_password": "Senha123",
            "new_password": "NovaSenha456",
            "confirm_password": "NovaSenha456",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("user_detail", kwargs={"pk": user.pk})
