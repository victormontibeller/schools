"""Testes das views inline de turmas."""

import pytest
from django.urls import reverse

from classes.models import Class, Enrollment
from core.models import CustomUser
from students.models import Student
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
def test_class_list_detail_search_and_enroll_flow(client, user):
    client.force_login(user)
    cls = Class.objects.create(
        name="Busca 2A",
        grade=Class.Grade.ELEMENTARY_2,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        shift=Class.Shift.MORNING,
        academic_year=2026,
        max_students=30,
        created_by=user,
        updated_by=user,
    )
    student = Student.objects.create(
        first_name="Aluno",
        last_name="Disponível",
        birth_date="2016-01-01",
        enrollment_number="CLASS-VIEW-001",
        created_by=user,
        updated_by=user,
    )

    list_response = client.get(reverse("classes_list"), {"q": "Busca"})
    partial_response = client.get(reverse("classes_list"), HTTP_HX_REQUEST="true")
    detail_response = client.get(reverse("class_detail", args=[cls.pk]))
    information_response = client.get(
        reverse("class_detail", args=[cls.pk]),
        {"component": "information"},
        HTTP_HX_REQUEST="true",
    )
    search_response = client.get(
        reverse("class_student_search", args=[cls.pk]), {"q": "Disponível"}
    )
    enroll_response = client.post(
        reverse("class_enroll", args=[cls.pk]), {"student_id": student.pk}
    )

    assert list_response.status_code == 200
    assert partial_response.status_code == 200
    assert detail_response.status_code == 200
    assert information_response.status_code == 200
    assert search_response.status_code == 200
    assert enroll_response.status_code == 302
    assert Enrollment.objects.filter(class_obj=cls, student=student).exists()


@pytest.mark.django_db
def test_class_edit_post_updates_and_returns_information_card(client, user):
    client.force_login(user)
    teacher_user = CustomUser.objects.create_user(
        email="class-edit-view@example.com", password="Senha123"
    )
    teacher = Teacher.objects.create(
        user=teacher_user,
        registration_number="CLASS-EDIT-VIEW",
        created_by=user,
        updated_by=user,
    )
    cls = Class.objects.create(
        name="3A",
        grade=Class.Grade.ELEMENTARY_3,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        shift=Class.Shift.MORNING,
        academic_year=2026,
        max_students=30,
        class_teacher=teacher,
        created_by=user,
        updated_by=user,
    )

    response = client.post(
        reverse("class_edit", args=[cls.pk]),
        {
            "name": "3A Atualizada",
            "grade": Class.Grade.ELEMENTARY_3,
            "education_stage": Class.EducationStage.ELEMENTARY_I,
            "shift": Class.Shift.AFTERNOON,
            "academic_year": 2026,
            "max_students": 25,
            "class_teacher": teacher.pk,
            "version": cls.version,
        },
        HTTP_HX_REQUEST="true",
    )

    cls.refresh_from_db()
    assert response.status_code == 200
    assert cls.name == "3A Atualizada"
    assert b"atualizadas com sucesso" in response.content
