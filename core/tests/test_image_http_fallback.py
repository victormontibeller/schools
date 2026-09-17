"""Entradas e erros de upload preservam uma página utilizável sem JavaScript."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from base.tests.factories import StudentFactory
from core.models import CustomUser
from teachers.models import Teacher


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["user", "teacher", "student", "guardian"])
def test_get_edit_and_invalid_upload_render_full_page(client, user, kind):
    client.force_login(user)
    if kind == "user":
        edit = reverse("user_edit", args=[user.pk])
        detail = reverse("user_detail", args=[user.pk])
        field = "avatar"
    elif kind == "teacher":
        target = CustomUser.objects.create_user(email="teacher@test.test", password="Senha123")
        teacher = Teacher.objects.create(user=target, registration_number="TEST")
        edit = reverse("teacher_edit", args=[teacher.pk])
        detail = reverse("teacher_detail", args=[teacher.pk])
        field = "avatar"
    else:
        student = StudentFactory()
        edit = reverse(
            "student_edit" if kind == "student" else "student_guardian_create", args=[student.pk]
        )
        detail = reverse("student_profile", args=[student.pk])
        field = "photo" if kind == "student" else "avatar"
    assert f'href="{edit}"'.encode() in client.get(detail).content
    response = client.get(edit)
    assert response.status_code == 200
    assert b"<html" in response.content
    assert f'action="{edit}"'.encode() in response.content
    assert b'method="post"' in response.content
    assert b'enctype="multipart/form-data"' in response.content
    response = client.post(edit, {field: SimpleUploadedFile("bad.png", b"bad", "image/png")})
    assert response.status_code == 200
    assert b"<html" in response.content
    assert "Arquivo de imagem inválido." in response.content.decode()
    assert f'action="{edit}"'.encode() in response.content
    partial = client.get(edit, HTTP_HX_REQUEST="true")
    assert b"<html" not in partial.content
