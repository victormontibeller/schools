"""Testes dos storages e endpoints de mídia pública/privada."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from base import context
from base.media import delete_replaced_file_after_commit, student_photo_path
from base.tests.images import png_upload


def test_media_path_uses_schema_category_and_uuid_without_original_name():
    token = context.current_tenant.set("escola_a")
    try:
        path = student_photo_path(object(), "Nome da Pessoa.png")
    finally:
        context.current_tenant.reset(token)

    assert path.startswith("escola_a/photos/students/")
    assert path.endswith(".png")
    assert "Nome" not in path
    assert len(path.rsplit("/", maxsplit=1)[-1].removesuffix(".png")) == 32


def test_replaced_file_is_deleted_only_by_post_commit_callback(monkeypatch):
    callbacks = []

    class StorageSpy:
        deleted = []

        def delete(self, name):
            self.deleted.append(name)

    storage = StorageSpy()
    monkeypatch.setattr("base.media.transaction.on_commit", callbacks.append)

    delete_replaced_file_after_commit(storage, "tenant/avatar/old.png", "tenant/avatar/new.png")

    assert storage.deleted == []
    assert len(callbacks) == 1
    callbacks[0]()
    assert storage.deleted == ["tenant/avatar/old.png"]


@pytest.mark.django_db
def test_logo_is_public_but_avatar_has_no_public_url(user):
    from tenancy.models import School

    school = School.objects.create(schema_name="media_school", name="Escola Mídia")
    school.logo.save("nome-da-escola.png", png_upload("logo.png"), save=True)
    user.avatar.save("nome-da-pessoa.png", png_upload(), save=True)
    try:
        assert school.logo.url.startswith("/media/")
        with pytest.raises(ValueError):
            _ = user.avatar.url
    finally:
        school.logo.delete(save=False)
        user.avatar.delete(save=False)


@pytest.mark.django_db
def test_own_avatar_is_inline_private_and_not_reachable_under_media(client, user):
    user.avatar.save("avatar.png", png_upload(), save=True)
    client.force_login(user)
    try:
        response = client.get(reverse("user_avatar", args=[user.pk]))
        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store"
        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["Content-Disposition"].startswith("inline;")
        response.close()
        assert client.get(f"/media/{user.avatar.name}").status_code == 404
    finally:
        user.avatar.delete(save=False)


@pytest.mark.django_db
def test_unrelated_guardian_cannot_access_student_photo(client, user):
    from core.models import CustomUser, Role
    from students.models import Student

    role, _ = Role.objects.get_or_create(name=Role.Name.GUARDIAN)
    outsider = CustomUser.objects.create_user(
        email="outsider@test.com",
        password="Senha123",
        first_name="Outro",
        last_name="Responsável",
        role=role,
    )
    student = Student.objects.create(
        enrollment_number="ALU-MEDIA-1",
        first_name="Aluno",
        last_name="Privado",
        birth_date="2015-01-01",
        photo=png_upload("student.png"),
        created_by=user,
        updated_by=user,
    )
    client.force_login(outsider)
    try:
        assert client.get(reverse("student_photo", args=[student.pk])).status_code == 403
    finally:
        student.photo.delete(save=False)


@pytest.mark.django_db
def test_attendance_document_is_protected_attachment(client, user):
    from attendance.models import AttendanceJustification
    from students.models import Student

    student = Student.objects.create(
        enrollment_number="ALU-MEDIA-2",
        first_name="Aluno",
        last_name="Documento",
        birth_date="2015-01-01",
        created_by=user,
        updated_by=user,
    )
    justification = AttendanceJustification.objects.create(
        student=student,
        start_date="2026-07-13",
        end_date="2026-07-13",
        reason="Atendimento",
        document=SimpleUploadedFile("atestado.pdf", b"%PDF-1.4\n", "application/pdf"),
        created_by=user,
        updated_by=user,
    )
    client.force_login(user)
    try:
        response = client.get(reverse("justification_document", args=[justification.pk]))
        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store"
        assert response["Content-Disposition"].startswith("attachment;")
        response.close()
    finally:
        justification.document.delete(save=False)
