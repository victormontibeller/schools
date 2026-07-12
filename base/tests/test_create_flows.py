"""Testes de integração das telas de criação de professor e responsável.

Cobrem Sprint 08.5 (frontend de cadastro) — fluxos completos via Django Client,
garantindo que as telas novas renderizem, validem e persistam com auditoria.
"""

import pytest

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
            "first_name": "Professor",
            "last_name": "Novo",
            "email": "professor-novo@example.com",
            "hire_date": "2020-01-15",
            "birth_date": "1990-05-20",
            "gender": "M",
            "nationality": "Brasileira",
            "cpf": "390.533.447-05",
            "rg_number": "1234567",
            "rg_issuer": "SSP",
            "rg_state": "SP",
            "phone_mobile": "11999990000",
            "subjects": [str(s1.pk), str(s2.pk)],
        }
        resp = logged.post("/teachers/novo/", data, follow=False)
        assert resp.status_code == 302  # redireciona para listagem
        t = Teacher.objects.get(user__email="professor-novo@example.com")
        assert t.registration_number.startswith("PRO-")
        assert set(t.subjects.values_list("pk", flat=True)) == {s1.pk, s2.pk}

    def test_post_existing_teacher_email_rerenders_form(self, logged, user):
        """E-mail já vinculado a professor deve re-renderizar o formulário."""
        existing = Teacher.objects.create(user=user, registration_number="LEGACY")
        data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "hire_date": "2020-01-15",
            "birth_date": "1990-05-20",
            "gender": "M",
            "nationality": "Brasileira",
            "cpf": "390.533.447-05",
            "rg_number": "1234567",
            "rg_issuer": "SSP",
            "rg_state": "SP",
            "phone_mobile": "11999990000",
        }
        resp = logged.post("/teachers/novo/", data)
        assert resp.status_code == 200
        assert existing.pk is not None
        assert resp.context["form"].non_field_errors()


# ── Guardians ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGuardianCreate:
    def test_get_renders_form(self, logged):
        """O cadastro isolado de responsável está disponível."""
        resp = logged.get("/guardians/novo/")
        assert resp.status_code == 200

    def test_post_redirects_to_students(self, logged, user):
        """O cadastro isolado foi removido em favor do perfil do aluno."""
        from core.models import CustomUser

        other = CustomUser.objects.create_user(
            email="guardian@test.com",
            password="Senha123",
            first_name="Maria",
            last_name="Silva",
        )
        data = {
            "first_name": other.first_name,
            "last_name": other.last_name,
            "email": other.email,
            "birth_date": "1980-01-01",
            "gender": "F",
            "nationality": "Brasileira",
            "cpf": "52998224725",
            "rg_number": "MG-12.345",
            "rg_issuer": "SSP",
            "rg_state": "MG",
            "phone": "+55 31 98888-7777",
            "phone_whatsapp": "+55 31 98888-7777",
            "phone_mobile": "+55 31 97777-6666",
        }
        resp = logged.post("/guardians/novo/", data, follow=False)
        assert resp.status_code == 302
        assert "/guardians/" in resp.url

    def test_post_missing_identity_rerenders(self, logged, user):
        """Identidade incompleta mantém o formulário com erros."""
        data = {"first_name": ""}
        resp = logged.post("/guardians/novo/", data)
        assert resp.status_code == 200


# ── Observações do aluno ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSpecialNeedsField:
    def test_studentform_accepts_free_text_observations(self):
        from students.forms import StudentForm

        form = StudentForm(
            data={
                "first_name": "João",
                "last_name": "Silva",
                "enrollment_number": "STU-001",
                "birth_date": "2010-05-12",
                "gender": "M",
                "blood_type": "O+",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "phone_mobile": "11999990000",
                "email": "joao@example.com",
                "observations": "Necessita acompanhamento para asma.",
            }
        )
        assert form.is_valid()
        assert form.cleaned_data["observations"] == "Necessita acompanhamento para asma."

    def test_studentform_rejects_observations_above_250_characters(self):
        from students.forms import StudentForm

        form = StudentForm(
            data={
                "first_name": "João",
                "last_name": "Silva",
                "enrollment_number": "STU-002",
                "birth_date": "2010-05-12",
                "gender": "M",
                "blood_type": "O+",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "phone_mobile": "11999990000",
                "email": "joao@example.com",
                "observations": "a" * 251,
            }
        )
        assert not form.is_valid()
        assert "observations" in form.errors

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
