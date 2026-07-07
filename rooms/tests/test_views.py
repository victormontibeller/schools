"""Testes de integracao das views de salas."""

import pytest


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
            "resources": '{"projetor": true}',
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
