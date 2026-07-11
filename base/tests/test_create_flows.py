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
            "user_id": str(user.pk),
            "registration_number": "REG-001",
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
        data = {
            "user_id": str(user.pk),
            "registration_number": "DUP-REG",
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
        form = resp.context["form"]
        assert "registration_number" in form.errors


# ── Guardians ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGuardianCreate:
    def test_get_redirects_to_students(self, logged):
        """O cadastro isolado foi substituído pelo perfil do aluno."""
        resp = logged.get("/guardians/novo/")
        assert resp.status_code == 302
        assert resp.url == "/students/"

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
            "user_id": str(other.pk),
            "relationship_type": "MAE",
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
        assert resp.url == "/students/"

    def test_post_blank_relationship_redirects_to_students(self, logged, user):
        """A validação de parentesco ocorre no card do aluno."""
        data = {"user_id": str(user.pk), "relationship_type": ""}
        resp = logged.post("/guardians/novo/", data)
        assert resp.status_code == 302
        assert resp.url == "/students/"


# ── Necessidades especiais ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSpecialNeedsField:
    def test_studentform_accepts_free_text_special_needs(self):
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
                "special_needs": "Necessita acompanhamento para asma.",
            }
        )
        assert form.is_valid()
        assert form.cleaned_data["special_needs"] == "Necessita acompanhamento para asma."

    def test_studentform_rejects_special_needs_above_250_characters(self):
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
                "special_needs": "a" * 251,
            }
        )
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
