"""Testes de integracao das views de disciplinas."""

import pytest

from core.models import CustomUser
from teachers.models import Subject
from teachers.services import TeacherService


@pytest.fixture()
def force_login_client(client, user, db):
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestSubjectViews:
    def _make_subject(self, code="TST"):
        from teachers.models import Subject

        return Subject.objects.create(name="Teste", code=code, workload=40)

    def test_subjects_list_renders(self, force_login_client):
        self._make_subject()
        resp = force_login_client.get("/subjects/")
        assert resp.status_code == 200
        assert b"Disciplinas" in resp.content

    def test_subject_create_get_renders_form(self, force_login_client):
        resp = force_login_client.get("/subjects/novo/")
        assert resp.status_code == 200
        assert b"form" in resp.content.lower()

    def test_subject_create_post_creates_and_redirects(self, force_login_client):
        data = {"name": "Fisica", "code": "FIS", "workload": 60}
        resp = force_login_client.post("/subjects/novo/", data)
        assert resp.status_code == 302
        from teachers.models import Subject

        assert Subject.objects.filter(code="FIS").exists()

    def test_subject_create_post_duplicate_rerenders(self, force_login_client):
        self._make_subject(code="DUP")
        data = {"name": "Outra", "code": "DUP", "workload": 40}
        resp = force_login_client.post("/subjects/novo/", data)
        assert resp.status_code == 200
        assert resp.context["form"].errors

    def test_subject_edit_get_renders_form(self, force_login_client):
        sub = self._make_subject(code="FIS-EDT")
        resp = force_login_client.get(f"/subjects/{sub.pk}/editar/")
        assert resp.status_code == 200
        assert b"form" in resp.content.lower()

    def test_subject_edit_post_updates_and_redirects(self, force_login_client):
        sub = self._make_subject(code="FIS-UPD")
        data = {"name": "Fisica Avancada", "code": "FIS-UPD", "workload": 80}
        resp = force_login_client.post(f"/subjects/{sub.pk}/editar/", data)
        assert resp.status_code == 302
        sub.refresh_from_db()
        assert sub.name == "Fisica Avancada"

    def test_subject_deactivate_post_redirects(self, force_login_client):
        sub = self._make_subject(code="FIS-DEA")
        resp = force_login_client.post(f"/subjects/{sub.pk}/desativar/")
        assert resp.status_code == 302


@pytest.mark.django_db
class TestTeacherInlineEditing:
    def _make_teacher(self, user):
        target = CustomUser.objects.create_user(
            email="inline-teacher@example.com",
            password="Senha123",
            first_name="Professor",
            last_name="Inline",
        )
        return TeacherService(user=user).create_teacher(
            {"user_id": target.pk, "registration_number": "INLINE-001"}
        )

    def test_detail_exposes_inline_edit_and_subject_actions(self, force_login_client, user):
        teacher = self._make_teacher(user)

        response = force_login_client.get(f"/teachers/{teacher.pk}/")

        assert response.status_code == 200
        assert b'hx-target="#teacher-information-card"' in response.content
        assert b'hx-target="#teacher-subjects-card"' in response.content

    def test_edit_get_returns_only_component_for_htmx(self, force_login_client, user):
        teacher = self._make_teacher(user)

        response = force_login_client.get(
            f"/teachers/{teacher.pk}/editar/",
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert b"Editar Informa" in response.content
        assert b"<html" not in response.content

    def test_edit_post_updates_and_returns_card_for_htmx(self, force_login_client, user):
        teacher = self._make_teacher(user)

        response = force_login_client.post(
            f"/teachers/{teacher.pk}/editar/",
            {"registration_number": "INLINE-002"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        teacher.refresh_from_db()
        assert teacher.registration_number == "INLINE-002"
        assert b"atualizadas com sucesso" in response.content

    def test_subjects_post_replaces_links_and_returns_card(self, force_login_client, user):
        teacher = self._make_teacher(user)
        subject = Subject.objects.create(
            name="Geografia",
            code="GEO-INLINE",
            created_by=user,
            updated_by=user,
        )

        response = force_login_client.post(
            f"/teachers/{teacher.pk}/editar/?component=subjects",
            {"subjects": [str(subject.pk)]},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert teacher.subjects.filter(pk=subject.pk).exists()
        assert b"Geografia" in response.content

    def test_subjects_get_returns_inline_form(self, force_login_client, user):
        teacher = self._make_teacher(user)

        response = force_login_client.get(
            f"/teachers/{teacher.pk}/editar/?component=subjects",
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert b"Vincular Disciplinas" in response.content
        assert b"<select" in response.content
