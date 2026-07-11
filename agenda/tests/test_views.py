"""Testes das telas de horários."""

import datetime as dt

import pytest
from django.urls import reverse

from agenda.models import TimeSlot


@pytest.mark.django_db
def test_time_slots_list_uses_shared_listing_pattern(client, user):
    client.force_login(user)
    TimeSlot.objects.create(
        day_of_week=TimeSlot.Day.MON,
        slot_number=1,
        start_time=dt.time(8, 0),
        end_time=dt.time(9, 0),
        created_by=user,
        updated_by=user,
    )

    response = client.get(reverse("time_slots_list"))
    partial_response = client.get(reverse("time_slots_list"), HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Lista de Hor" in response.content
    assert b"NOVO" in response.content
    assert f"/horarios/{TimeSlot.objects.first().pk}/editar/".encode() in response.content
    assert partial_response.status_code == 200
    assert b"<html" not in partial_response.content


@pytest.mark.django_db
def test_time_slot_create_uses_compact_form_card(client, user):
    client.force_login(user)

    response = client.get(reverse("time_slot_create"))

    assert response.status_code == 200
    assert b"col-12 col-xl-5" in response.content
    assert b"row g-2" in response.content
