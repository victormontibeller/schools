"""Testes de integracao das views de disciplinas."""

import pytest
from django.utils import timezone

from base.tests.images import png_upload
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

    def test_subjects_list_includes_inactive_subjects_with_status(self, force_login_client):
        Subject.all_objects.create(name="Inativa", code="INAT", workload=40, is_active=False)
        Subject.all_objects.create(
            name="Removida",
            code="REM",
            workload=40,
            is_active=False,
            deleted_at=timezone.now(),
        )

        response = force_login_client.get("/subjects/")

        assert response.status_code == 200
        assert b"Inativa" in response.content
        assert b"Inativa</span>" in response.content
        assert b"Removida" not in response.content

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
        data = {
            "name": "Fisica Avancada",
            "code": "FIS-UPD",
            "workload": 80,
            "is_active": "on",
        }
        resp = force_login_client.post(f"/subjects/{sub.pk}/editar/", data)
        assert resp.status_code == 302
        sub.refresh_from_db()
        assert sub.name == "Fisica Avancada"
        assert sub.is_active is True

    def test_subject_edit_switches_active_status_without_separate_action(self, force_login_client):
        subject = self._make_subject(code="FIS-STA")

        form_response = force_login_client.get(
            f"/subjects/{subject.pk}/editar/",
            HTTP_HX_REQUEST="true",
        )
        deactivate_response = force_login_client.post(
            f"/subjects/{subject.pk}/editar/",
            {"name": "Teste", "code": "FIS-STA", "workload": 40},
            HTTP_HX_REQUEST="true",
        )

        subject.refresh_from_db()
        assert b'name="is_active"' in form_response.content
        assert b"Desativar" not in form_response.content
        assert deactivate_response.status_code == 200
        assert subject.is_active is False
        assert b"Inativa" in deactivate_response.content

        reactivate_response = force_login_client.post(
            f"/subjects/{subject.pk}/editar/",
            {
                "name": "Teste",
                "code": "FIS-STA",
                "workload": 40,
                "is_active": "on",
            },
            HTTP_HX_REQUEST="true",
        )

        subject.refresh_from_db()
        assert reactivate_response.status_code == 200
        assert subject.is_active is True


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
            {
                "first_name": target.first_name,
                "last_name": target.last_name,
                "email": target.email,
                "registration_number": "INLINE-001",
                "hire_date": "2020-01-15",
                "birth_date": "1990-05-20",
                "gender": "M",
                "nationality": "Brasileira",
                "cpf": "529.982.247-25",
                "rg_number": "1234567",
                "rg_issuer": "SSP",
                "rg_state": "SP",
                "phone_mobile": "11999990000",
            }
        )

    def test_detail_exposes_inline_edit_and_subject_actions(self, force_login_client, user):
        teacher = self._make_teacher(user)

        response = force_login_client.get(f"/teachers/{teacher.pk}/")

        assert response.status_code == 200
        assert b'hx-target="#teacher-information-card"' in response.content
        assert b'hx-target="#teacher-subjects-card"' in response.content
        assert b"sm-profile-hero" in response.content
        assert b"avatar-text" in response.content
        assert teacher.full_name.encode() in response.content
        assert teacher.email.encode() in response.content

    def test_edit_get_returns_only_component_for_htmx(self, force_login_client, user):
        teacher = self._make_teacher(user)

        response = force_login_client.get(
            f"/teachers/{teacher.pk}/editar/",
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert b"Informa" in response.content
        assert b"sm-profile-avatar-edit" in response.content
        assert b"sm-profile-avatar-input" in response.content
        assert teacher.full_name.encode() in response.content
        assert teacher.email.encode() in response.content
        assert b'name="email"' not in response.content
        assert b'name="email_display"' in response.content
        assert b"disabled" in response.content
        assert b"<html" not in response.content

    def test_edit_post_updates_and_returns_card_for_htmx(self, force_login_client, user):
        teacher = self._make_teacher(user)
        avatar = png_upload("inline-avatar.png")

        response = force_login_client.post(
            f"/teachers/{teacher.pk}/editar/",
            {
                "first_name": "Ana",
                "last_name": "Pereira",
                "email_display": "email-nao-deve-ser-alterado@example.com",
                "registration_number": "INLINE-002",
                "hire_date": "2025-01-15",
                "birth_date": "1990-05-20",
                "gender": "F",
                "nationality": "Brasileira",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "rg_issuer": "SSP",
                "rg_state": "SP",
                "phone_mobile": "(11) 99999-0000",
                "avatar": avatar,
                "version": teacher.version,
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        teacher.refresh_from_db()
        teacher.user.refresh_from_db()
        assert teacher.registration_number.startswith("PRO-")
        assert teacher.user.first_name == "Ana"
        assert teacher.user.email == "inline-teacher@example.com"
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
        assert b"Disciplinas" in response.content
        assert b"<select" in response.content

    def test_subject_edit_get_returns_inline_row(self, force_login_client, user):
        subject = Subject.objects.create(
            name="História",
            code="INLINE-ROW",
            created_by=user,
            updated_by=user,
        )

        response = force_login_client.get(
            f"/subjects/{subject.pk}/editar/",
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert b"Cancelar" in response.content
        assert b"<html" not in response.content
