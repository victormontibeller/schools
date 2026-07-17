"""Testes das views de consulta de usuários."""

import pytest
from django.core import mail
from django.test import override_settings
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


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_password_reset_uses_django_email_backend(client, listed_user):
    response = client.post(reverse("password_reset"), {"email": listed_user.email})

    assert response.status_code == 302
    assert response.url == reverse("password_reset_done")
    assert len(mail.outbox) == 1
    assert "/password-reset/confirm/" in mail.outbox[0].body


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["platform.localhost"])
def test_platform_operator_list_renders_full_and_htmx(client, user, listed_user):
    client.force_login(user)
    url = reverse("platform_user_list")

    response = client.get(url, HTTP_HOST="platform.localhost")
    partial = client.get(
        url,
        {"q": "Listado", "sort": "-email"},
        HTTP_HOST="platform.localhost",
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert partial.status_code == 200
    assert b"<html" not in partial.content
    assert str(listed_user.pk).encode() in partial.content


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["platform.localhost"])
def test_platform_operator_create_rejects_common_password_in_form(client, user):
    client.force_login(user)

    response = client.post(
        reverse("platform_user_create"),
        {
            "first_name": "Novo",
            "last_name": "Operador",
            "email": "novo-platform@example.com",
            "password": "password",
            "confirm_password": "password",
        },
        HTTP_HOST="platform.localhost",
    )

    assert response.status_code == 200
    assert CustomUser.objects.filter(email="novo-platform@example.com").exists() is False
    assert b"muito comum" in response.content


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["platform.localhost"])
def test_platform_operator_edit_get_and_post(client, user, listed_user):
    client.force_login(user)
    url = reverse("platform_user_edit", args=[listed_user.pk])

    get_response = client.get(url, HTTP_HOST="platform.localhost")
    post_response = client.post(
        url,
        {
            "first_name": "Operador",
            "last_name": "Atualizado",
            "is_active": "on",
            "is_superuser": "on",
        },
        HTTP_HOST="platform.localhost",
    )

    listed_user.refresh_from_db()
    assert get_response.status_code == 200
    assert post_response.status_code == 302
    assert listed_user.last_name == "Atualizado"
    assert listed_user.is_superuser is True


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["platform.localhost"])
def test_platform_operator_management_rejects_non_superuser(client, user):
    user.is_superuser = False
    user.save(update_fields=["is_superuser"])
    client.force_login(user)

    response = client.get(reverse("platform_user_list"), HTTP_HOST="platform.localhost")

    assert response.status_code == 403
