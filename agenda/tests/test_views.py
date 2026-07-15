"""Testes das telas de horários."""

import datetime as dt

import pytest
from django.urls import reverse

from agenda.models import Schedule, TimeSlot
from classes.models import Class
from core.models import CustomUser
from rooms.models import Room
from teachers.models import Subject, Teacher


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


@pytest.mark.django_db
def test_time_slot_create_and_edit_posts(client, user):
    client.force_login(user)
    create_response = client.post(
        reverse("time_slot_create"),
        {
            "day_of_week": TimeSlot.Day.TUE,
            "slot_number": 2,
            "start_time": "09:00",
            "end_time": "10:00",
        },
    )
    slot = TimeSlot.objects.get(day_of_week=TimeSlot.Day.TUE)
    edit_response = client.post(
        reverse("time_slot_edit", args=[slot.pk]),
        {
            "day_of_week": TimeSlot.Day.TUE,
            "slot_number": 3,
            "start_time": "09:00",
            "end_time": "10:00",
        },
    )

    slot.refresh_from_db()
    assert create_response.status_code == 302
    assert edit_response.status_code == 302
    assert slot.slot_number == 3


@pytest.mark.django_db
def test_schedule_create_and_weekly_teacher_views(client, user):
    client.force_login(user)
    cls = Class.objects.create(
        name="Grade 4A",
        grade=Class.Grade.ELEMENTARY_4,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    teacher_user = CustomUser.objects.create_user(
        email="schedule-view@example.com", password="Senha123"
    )
    teacher = Teacher.objects.create(
        user=teacher_user,
        registration_number="SCHEDULE-VIEW",
        created_by=user,
        updated_by=user,
    )
    subject = Subject.objects.create(
        name="Ciências", code="SCI-VIEW", created_by=user, updated_by=user
    )
    teacher.subjects.add(subject)
    room = Room.objects.create(name="Sala da Grade", code="GRADE-ROOM", capacity=30)
    slot = TimeSlot.objects.create(
        day_of_week=TimeSlot.Day.WED,
        slot_number=1,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )

    create_response = client.post(
        reverse("schedule_create", args=[cls.pk]),
        {
            "teacher": teacher.pk,
            "subject": subject.pk,
            "time_slot": slot.pk,
            "room": room.pk,
            "valid_from": "2026-01-20",
            "valid_until": "2026-12-10",
        },
    )
    weekly_response = client.get(reverse("schedule_weekly", args=[cls.pk]))
    teacher_response = client.get(reverse("teacher_schedule", args=[teacher.pk]))

    assert create_response.status_code == 302
    assert weekly_response.status_code == 200
    assert teacher_response.status_code == 200
    assert Schedule.objects.filter(class_obj=cls, teacher=teacher).exists()
