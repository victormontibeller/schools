"""Testes das views inline de turmas."""

import pytest

from classes.models import Class


@pytest.mark.django_db
def test_class_edit_get_returns_only_component_for_htmx(client, user):
    client.force_login(user)
    cls = Class.objects.create(
        name="1A",
        grade="1º Ano",
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )

    response = client.get(f"/classes/{cls.pk}/editar/", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Cancelar" in response.content
    assert b"<html" not in response.content
