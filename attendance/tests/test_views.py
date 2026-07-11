"""Testes das respostas HTMX da chamada."""

import datetime as dt

import pytest
from django.urls import reverse

from attendance.services import AttendanceService
from classes.models import Class, Enrollment
from core.models import CustomUser
from students.models import Student
from teachers.models import Subject, Teacher


@pytest.mark.django_db
def test_attendance_records_list_uses_shared_listing_pattern(client, user):
    client.force_login(user)

    response = client.get(reverse("attendance_records_list"))
    partial_response = client.get(reverse("attendance_records_list"), HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Lista de Frequ" in response.content
    assert b"NOVO" in response.content
    assert partial_response.status_code == 200
    assert b"<html" not in partial_response.content


@pytest.mark.django_db
def test_justifications_list_preserves_status_filter_in_shared_header(client, user):
    client.force_login(user)

    response = client.get(reverse("justifications_list"), {"status": "PENDING"})

    assert response.status_code == 200
    assert b"Lista de Justificativas" in response.content
    assert b'name="status"' in response.content


@pytest.mark.django_db
def test_attendance_fill_post_returns_only_card_for_htmx(client, user):
    client.force_login(user)
    cls = Class.objects.create(
        name="3A",
        grade="3º Ano",
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    subject = Subject.objects.create(name="Artes", code="ART", created_by=user, updated_by=user)
    teacher_user = CustomUser.objects.create_user(
        email="attendance-view@example.com",
        password="Senha123",
    )
    teacher = Teacher.objects.create(
        user=teacher_user,
        registration_number="ATT-VIEW",
        created_by=user,
        updated_by=user,
    )
    student = Student.objects.create(
        first_name="Aluno",
        last_name="Teste",
        birth_date=dt.date(2015, 1, 1),
        enrollment_number="ATT-STUDENT",
        created_by=user,
        updated_by=user,
    )
    Enrollment.objects.create(
        student=student,
        class_obj=cls,
        enrollment_date=dt.date.today(),
        status=Enrollment.Status.ACTIVE,
        created_by=user,
        updated_by=user,
    )
    record = AttendanceService(user=user).open_attendance(
        {
            "class_id": cls.pk,
            "subject_id": subject.pk,
            "teacher_id": teacher.pk,
            "date": dt.date(2026, 7, 2),
        }
    )

    response = client.post(
        f"/frequencia/{record.pk}/chamada/",
        {f"status_{student.pk}": "ABSENT"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Chamada salva com sucesso" in response.content
    assert b"<html" not in response.content
