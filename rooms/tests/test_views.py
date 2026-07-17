"""Testes de integracao das views de salas."""

import pytest
from django.urls import reverse


@pytest.fixture()
def force_login_client(client, user, db):
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestRoomViews:
    def _make_room(self, code="SALA01"):
        from rooms.models import Room

        return Room.objects.create(name="Sala Teste", code=code, capacity=30)

    def test_rooms_list_renders(self, force_login_client):
        self._make_room()
        resp = force_login_client.get("/rooms/")
        assert resp.status_code == 200
        assert b"SALA01" in resp.content

    def test_room_create_get_renders_form(self, force_login_client):
        resp = force_login_client.get("/rooms/nova/")
        assert resp.status_code == 200
        assert b"form" in resp.content.lower()

    def test_room_create_post_creates_and_redirects(self, force_login_client):
        data = {
            "name": "Sala 202",
            "code": "SL202",
            "capacity": 30,
            "type": "CLASSROOM",
            "floor": "2",
            "building": "Bloco A",
            "observations": "Possui projetor",
        }
        resp = force_login_client.post("/rooms/nova/", data)
        assert resp.status_code == 302
        from rooms.models import Room

        assert Room.objects.filter(code="SL202").exists()

    def test_rooms_list_requires_login(self, client):
        assert client.get("/rooms/").status_code == 302

    def test_room_edit_get_returns_only_component_for_htmx(self, force_login_client):
        room = self._make_room()

        resp = force_login_client.get(
            f"/rooms/{room.pk}/editar/",
            HTTP_HX_REQUEST="true",
        )

        assert resp.status_code == 200
        assert b"Cancelar" in resp.content
        assert b"<html" not in resp.content

    def test_room_detail_components_and_edit_post(self, force_login_client):
        room = self._make_room(code="SALA02")

        detail = force_login_client.get(reverse("room_detail", args=[room.pk]))
        component = force_login_client.get(
            reverse("room_detail", args=[room.pk]),
            {"component": "information"},
            HTTP_HX_REQUEST="true",
        )
        edited = force_login_client.post(
            reverse("room_edit", args=[room.pk]),
            {
                "name": "Sala Atualizada",
                "code": "SALA02",
                "capacity": 25,
                "type": "CLASSROOM",
                "floor": "2",
                "building": "Bloco B",
                "observations": "",
                "version": room.version,
            },
            HTTP_HX_REQUEST="true",
        )

        room.refresh_from_db()
        assert detail.status_code == 200
        assert component.status_code == 200
        assert edited.status_code == 200
        assert room.name == "Sala Atualizada"

    def test_rooms_list_htmx_and_non_htmx_edit_redirect(self, force_login_client):
        room = self._make_room(code="SALA03")

        partial = force_login_client.get(
            reverse("rooms_list"), {"q": "Sala"}, HTTP_HX_REQUEST="true"
        )
        redirect_response = force_login_client.get(reverse("room_edit", args=[room.pk]))

        assert partial.status_code == 200
        assert b"<html" not in partial.content
        assert redirect_response.status_code == 302

    def test_secretary_can_list_create_and_edit_rooms(self, client):
        from core.models import CustomUser, Role
        from rooms.models import Room

        secretary = CustomUser.objects.create_user(
            email="secretary-rooms@test.com",
            password="Senha123",
            role=Role.objects.get(name=Role.Name.SECRETARY),
        )
        client.force_login(secretary)

        listing = client.get(reverse("rooms_list"))
        created = client.post(
            reverse("room_create"),
            {
                "name": "Sala Secretaria",
                "code": "SEC01",
                "capacity": 20,
                "type": "CLASSROOM",
                "floor": "1",
                "building": "Bloco A",
                "observations": "",
            },
        )
        room = Room.objects.get(code="SEC01")
        edited = client.post(
            reverse("room_edit", args=[room.pk]),
            {
                "name": "Sala Secretaria Atualizada",
                "code": "SEC01",
                "capacity": 22,
                "type": "CLASSROOM",
                "floor": "1",
                "building": "Bloco A",
                "observations": "",
                "version": room.version,
            },
            HTTP_HX_REQUEST="true",
        )
        room.refresh_from_db()

        assert listing.status_code == 200
        assert created.status_code == 302
        assert edited.status_code == 200
        assert room.name == "Sala Secretaria Atualizada"
