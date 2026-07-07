"""Testes das views de listagem de responsáveis."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from core.models import CustomUser
from guardians.services import GuardianService


@pytest.fixture()
def force_login_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture()
def guardian(user):
    target = CustomUser.objects.create_user(
        email="guardian-view@example.com",
        password="Senha123",
        first_name="Carla",
        last_name="Listado",
    )
    return GuardianService(user=user).create_guardian(
        {
            "user_id": target.pk,
            "relationship_type": "MAE",
        }
    )


@pytest.mark.django_db
def test_guardians_list_persists_search_and_sort_in_session(force_login_client, guardian):
    response = force_login_client.get("/guardians/?q=Carla&sort=relationship_type")

    assert response.status_code == 200
    assert response.context["q"] == "Carla"
    assert response.context["sort"] == "relationship_type"
    assert force_login_client.session["listing_state"]["guardians_list"] == {
        "q": "Carla",
        "sort": "relationship_type",
    }


@pytest.mark.django_db
def test_guardians_list_restores_saved_state_when_query_is_omitted(force_login_client, guardian):
    session = force_login_client.session
    session["listing_state"] = {"guardians_list": {"q": "Carla", "sort": "relationship_type"}}
    session.save()

    response = force_login_client.get("/guardians/")

    assert response.status_code == 200
    assert response.context["q"] == "Carla"
    assert response.context["sort"] == "relationship_type"


@pytest.mark.django_db
def test_guardian_detail_exposes_inline_information_edit(force_login_client, guardian):
    response = force_login_client.get(f"/guardians/{guardian.pk}/")

    assert response.status_code == 200
    assert b'hx-target="#guardian-information-card"' in response.content


@pytest.mark.django_db
def test_guardian_edit_get_returns_only_component_for_htmx(force_login_client, guardian):
    response = force_login_client.get(
        f"/guardians/{guardian.pk}/editar/",
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Cancelar" in response.content
    assert b"Salvar" in response.content
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_guardian_edit_post_updates_and_returns_card_for_htmx(force_login_client, guardian):
    avatar = SimpleUploadedFile(
        "guardian.gif",
        (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
            b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00"
            b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        ),
        content_type="image/gif",
    )
    response = force_login_client.post(
        f"/guardians/{guardian.pk}/editar/",
        {
            "first_name": "Carla",
            "last_name": "Atualizada",
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
            "avatar": avatar,
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    guardian.refresh_from_db()
    guardian.user.refresh_from_db()
    assert guardian.relationship_type == "PAI"
    assert guardian.user.last_name == "Atualizada"
    assert guardian.user.avatar
    assert b"atualizadas com sucesso" in response.content
