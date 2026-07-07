"""Testes das views inline de atividades."""

import datetime as dt

import pytest

from activities.models import Activity
from classes.models import Class
from core.models import CustomUser
from teachers.models import Subject, Teacher


@pytest.mark.django_db
def test_activity_edit_get_returns_only_component_for_htmx(client, user):
    client.force_login(user)
    cls = Class.objects.create(
        name="2A",
        grade="2º Ano",
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    subject = Subject.objects.create(name="Ciências", code="CIE", created_by=user, updated_by=user)
    teacher_user = CustomUser.objects.create_user(
        email="activity-view@example.com",
        password="Senha123",
    )
    teacher = Teacher.objects.create(
        user=teacher_user,
        registration_number="ACT-VIEW",
        created_by=user,
        updated_by=user,
    )
    activity = Activity.objects.create(
        class_obj=cls,
        subject=subject,
        teacher=teacher,
        title="Experimento",
        due_date=dt.date(2026, 8, 10),
        created_by=user,
        updated_by=user,
    )

    response = client.get(f"/activities/{activity.pk}/editar/", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Cancelar" in response.content
    assert b"<html" not in response.content
