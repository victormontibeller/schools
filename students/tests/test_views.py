"""Testes das views de listagem de alunos."""

import pytest

from students.services import StudentService


@pytest.fixture()
def force_login_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture()
def student(user):
    return StudentService(user=user).create_student(
        {
            "first_name": "Ana",
            "last_name": "Listado",
            "birth_date": "2011-02-10",
            "enrollment_number": "STU-001",
            "gender": "F",
            "blood_type": "O+",
            "nationality": "Brasileira",
            "cpf": "529.982.247-25",
            "rg_number": "1234567",
            "rg_issuer": "SSP",
            "rg_state": "SP",
            "phone_mobile": "11999990000",
            "email": "ana-listado@example.com",
        }
    )


@pytest.mark.django_db
def test_students_list_persists_search_and_sort_in_session(force_login_client, student):
    response = force_login_client.get("/students/?q=Ana&sort=birth_date")

    assert response.status_code == 200
    assert response.context["q"] == "Ana"
    assert response.context["sort"] == "birth_date"
    assert force_login_client.session["listing_state"]["students_list"] == {
        "q": "Ana",
        "sort": "birth_date",
    }


@pytest.mark.django_db
def test_students_list_restores_saved_state_when_query_is_omitted(force_login_client, student):
    session = force_login_client.session
    session["listing_state"] = {"students_list": {"q": "Ana", "sort": "birth_date"}}
    session.save()

    response = force_login_client.get("/students/")

    assert response.status_code == 200
    assert response.context["q"] == "Ana"
    assert response.context["sort"] == "birth_date"


@pytest.mark.django_db
def test_student_profile_exposes_inline_information_edit(force_login_client, student):
    response = force_login_client.get(f"/students/{student.pk}/")

    assert response.status_code == 200
    assert b'hx-target="#student-information-card"' in response.content


@pytest.mark.django_db
def test_student_edit_get_returns_only_component_for_htmx(force_login_client, student):
    response = force_login_client.get(
        f"/students/{student.pk}/editar/",
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Cancelar" in response.content
    assert b"Salvar" in response.content
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_student_edit_post_updates_and_returns_card_for_htmx(force_login_client, student):
    response = force_login_client.post(
        f"/students/{student.pk}/editar/",
        {
            "enrollment_number": "STU-002",
            "first_name": "Ana",
            "last_name": "Atualizada",
            "birth_date": "2011-02-10",
            "gender": "F",
            "blood_type": "O+",
            "nationality": "Brasileira",
            "cpf": "390.533.447-05",
            "rg_number": "1234567",
            "rg_issuer": "SSP",
            "rg_state": "SP",
            "phone_mobile": "(11) 99999-0000",
            "email": "ana@example.com",
            "observations": "Asma; utilizar bombinha quando necessário.",
            "version": student.version,
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    student.refresh_from_db()
    assert student.last_name == "Atualizada"
    assert b"atualizadas com sucesso" in response.content


@pytest.mark.django_db
def test_student_profile_manages_guardians_inside_component(force_login_client, student):
    response = force_login_client.get(
        f"/students/{student.pk}/responsaveis/novo/", HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 200
    assert b"Novo respons" in response.content
    assert b"Buscar respons" in response.content
    assert "Já cadastrado".encode() not in response.content
    assert b"sm-profile-avatar-edit" in response.content


@pytest.mark.django_db
def test_student_profile_creates_and_links_guardian(force_login_client, student):
    response = force_login_client.post(
        f"/students/{student.pk}/responsaveis/novo/",
        {
            "first_name": "Carla",
            "last_name": "Contato",
            "email": "carla.contato@example.com",
            "relationship_type": "MAE",
            "is_primary": "on",
            "has_custody": "on",
            "can_pickup": "on",
            "birth_date": "1980-01-01",
            "gender": "F",
            "nationality": "Brasileira",
            "cpf": "390.533.447-05",
            "rg_number": "1234567",
            "rg_issuer": "SSP",
            "rg_state": "SP",
            "phone": "1133334444",
            "phone_whatsapp": "11999991111",
            "phone_mobile": "11988882222",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Carla Contato" in response.content
    assert student.guardians.count() == 1


@pytest.mark.django_db
def test_guardian_create_requires_email_but_not_avatar(force_login_client, student):
    data = {
        "first_name": "Carla",
        "last_name": "Contato",
        "relationship_type": "MAE",
        "birth_date": "1980-01-01",
        "gender": "F",
        "nationality": "Brasileira",
        "cpf": "390.533.447-05",
        "rg_number": "1234567",
        "rg_issuer": "SSP",
        "rg_state": "SP",
        "phone": "1133334444",
        "phone_whatsapp": "11999991111",
        "phone_mobile": "11988882222",
    }

    response = force_login_client.post(
        f"/students/{student.pk}/responsaveis/novo/", data, HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 200
    assert "Este campo é obrigatório".encode() in response.content
    assert student.guardians.count() == 0


@pytest.mark.django_db
def test_guardians_list_is_available(force_login_client):
    response = force_login_client.get("/guardians/")

    assert response.status_code == 200
    assert b"Respons" in response.content
