"""Testes das views inline de turmas."""

import pytest

from classes.models import Class
from core.models import CustomUser
from teachers.models import Teacher


@pytest.mark.django_db
def test_class_edit_get_returns_only_component_for_htmx(client, user):
    client.force_login(user)
    cls = Class.objects.create(
        name="1A",
        grade=Class.Grade.ELEMENTARY_1,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )

    response = client.get(f"/classes/{cls.pk}/editar/", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Cancelar" in response.content
    assert b'data-grade-select="true"' in response.content
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_class_create_renders_dependent_grade_select(client, user):
    client.force_login(user)

    response = client.get("/classes/nova/")

    assert response.status_code == 200
    assert b'<select name="grade"' in response.content
    assert b"data-grade-options=" in response.content
    assert response.content.index(b'name="education_stage"') < response.content.index(
        b'name="grade"'
    )


@pytest.mark.django_db
def test_class_create_accepts_valid_grade_without_javascript(client, user):
    client.force_login(user)
    teacher_user = CustomUser.objects.create_user(
        email="grade-form-teacher@test.com", password="Senha123"
    )
    teacher = Teacher.objects.create(
        user=teacher_user,
        registration_number="GRADE-FORM-TEACHER",
        created_by=user,
        updated_by=user,
    )

    response = client.post(
        "/classes/nova/",
        {
            "name": "1B",
            "education_stage": Class.EducationStage.ELEMENTARY_I,
            "grade": Class.Grade.ELEMENTARY_1,
            "shift": Class.Shift.MORNING,
            "academic_year": 2026,
            "max_students": 30,
            "class_teacher": teacher.pk,
        },
    )

    assert response.status_code == 302
    assert Class.objects.filter(name="1B", grade=Class.Grade.ELEMENTARY_1).exists()


@pytest.mark.django_db
def test_class_edit_legacy_grade_requires_structured_replacement(client, user):
    client.force_login(user)
    cls = Class.objects.create(
        name="Legada",
        grade="Série Experimental",
        education_stage=Class.EducationStage.OTHER,
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )

    response = client.get(f"/classes/{cls.pk}/editar/", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"valor legado" in response.content.lower()
    assert "Série Experimental" in response.content.decode()
