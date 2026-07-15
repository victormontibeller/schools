"""Testes dos campos obrigatórios de salas."""

import pytest

from rooms.forms import RoomForm


@pytest.mark.django_db
def test_room_form_requires_every_field():
    form = RoomForm(data={})

    assert not form.is_valid()
    for field_name in set(form.fields) - {"observations", "version"}:
        assert field_name in form.errors
