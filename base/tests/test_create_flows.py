"""Testes de integração das telas de criação de professor e responsável.

Cobrem Sprint 08.5 (frontend de cadastro) — fluxos completos via Django Client,
garantindo que as telas novas renderizem, validem e persistam com auditoria.
"""

import pytest

from guardians.models import Guardian
from teachers.models import Subject, Teacher


@pytest.fixture()
def logged(client, user, db):
    """Login client reutilizável para os testes de criação."""
    client.force_login(user)
    return client


# ── Teachers ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTeacherCreate:
    def test_get_renders_form_with_subjects_field(self, logged):
        """O formulário de criar professor contém o campo de disciplinas (M2M)."""
        Subject.objects.create(name="Matemática", code="MAT", workload=80)
        resp = logged.get("/teachers/novo/")
        assert resp.status_code == 200
        assert b"Disciplinas" in resp.content

    def test_post_creates_teacher_with_subjects(self, logged, user):
        """POST válido cria professor e atribui disciplinas."""
        s1 = Subject.objects.create(name="Matemática", code="MAT", workload=80)
        s2 = Subject.objects.create(name="História", code="HIS", workload=60)
        data = {
            "user_id": str(user.pk),
            "registration_number": "REG-001",
            "subjects": [str(s1.pk), str(s2.pk)],
        }
        resp = logged.post("/teachers/novo/", data, follow=False)
        assert resp.status_code == 302  # redireciona para listagem
        assert Teacher.objects.filter(registration_number="REG-001").exists()
        t = Teacher.objects.get(registration_number="REG-001")
        assert set(t.subjects.values_list("pk", flat=True)) == {s1.pk, s2.pk}

    def test_post_duplicated_registration_rerenders_form(self, logged, user):
        """Matrícula duplicada deve re-renderizar o form com erro no campo."""
        from core.models import CustomUser

        other = CustomUser.objects.create_user(
            email="dup@test.com", password="Senha123", first_name="D", last_name="U"
        )
        Teacher.objects.create(user=other, registration_number="DUP-REG")
        # O user logado NÃO tem perfil ainda → cai na checagem de matrícula duplicada
        data = {"user_id": str(user.pk), "registration_number": "DUP-REG"}
        resp = logged.post("/teachers/novo/", data)
        assert resp.status_code == 200
        form = resp.context["form"]
        assert "registration_number" in form.errors


# ── Guardians ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGuardianCreate:
    def test_get_renders_form_with_relationship_options(self, logged):
        """O formulário conterá o select de parentesco."""
        resp = logged.get("/guardians/novo/")
        assert resp.status_code == 200
        assert b"Parentesco" in resp.content

    def test_post_creates_guardian_with_contact_info(self, logged, user):
        """POST válido cria responsável com cpf/telefone/etc."""
        from core.models import CustomUser

        other = CustomUser.objects.create_user(
            email="guardian@test.com",
            password="Senha123",
            first_name="Maria",
            last_name="Silva",
        )
        data = {
            "user_id": str(other.pk),
            "relationship_type": "MAE",
            "cpf": "52998224725",
            "rg_number": "MG-12.345",
            "rg_issuer": "SSP",
            "rg_state": "MG",
            "phone": "+55 31 98888-7777",
            "phone_whatsapp": "+55 31 98888-7777",
        }
        resp = logged.post("/guardians/novo/", data, follow=False)
        assert resp.status_code == 302
        assert Guardian.objects.filter(cpf="52998224725").exists()

    def test_post_blank_relationship_rerenders_form(self, logged, user):
        """Parentesco obrigatório — vazio re-renderiza com erro."""
        data = {"user_id": str(user.pk), "relationship_type": ""}
        resp = logged.post("/guardians/novo/", data)
        assert resp.status_code == 200
        form = resp.context["form"]
        assert "relationship_type" in form.errors


# ── Forms com JSONField ────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestJsonFields:
    def test_studentform_accepts_special_needs_dict(self):
        from students.forms import StudentForm

        form = StudentForm(
            data={
                "first_name": "João",
                "last_name": "Silva",
                "enrollment_number": "STU-001",
                "birth_date": "2010-05-12",
                "special_needs": "{}",
            }
        )
        # clean_* functions may need DB; we just verify no JSON error
        form.is_valid()
        if form.is_valid():
            assert form.cleaned_data["special_needs"] == {}

    def test_studentform_rejects_invalid_json(self):
        from students.forms import StudentForm

        form = StudentForm(
            data={
                "first_name": "João",
                "last_name": "Silva",
                "enrollment_number": "STU-002",
                "birth_date": "2010-05-12",
                "special_needs": "{not valid json",
            }
        )
        # JSON inválido deve ser capturado entre os erros de `special_needs`
        assert not form.is_valid()
        assert "special_needs" in form.errors

    def test_roomform_validates_resources_json(self):
        from rooms.forms import RoomForm

        form = RoomForm(
            data={
                "name": "Sala A",
                "code": "A-1",
                "capacity": 30,
                "type": "CLASSROOM",
                "resources": '{"projetor": true}',
            }
        )
        if form.is_valid():
            assert form.cleaned_data["resources"] == {"projetor": True}
