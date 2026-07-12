"""Testes das views de listagem de responsáveis."""

import pytest

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
    response = force_login_client.get("/guardians/?q=Carla&sort=relationship_type")

    assert response.status_code == 200
    assert b"Carla" in response.content


@pytest.mark.django_db
def test_guardian_detail_renders(force_login_client, guardian):
    response = force_login_client.get(f"/guardians/{guardian.pk}/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_guardian_edit_renders_with_links(force_login_client, guardian):
    response = force_login_client.get(
        f"/guardians/{guardian.pk}/editar/",
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Alunos vinculados" in response.content


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
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 302
    guardian.refresh_from_db()
    assert guardian.last_name == "Atualizada"
