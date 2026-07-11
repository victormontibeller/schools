"""Testes de integração das views de professores, alunos e responsáveis.

Cobrem:
- Views exigem login (302 → /login/ sem sessão).
- Views listam objetos e renderizam templates.
- HTMX partials respondem com partial table.
- Detalhe mostra dados corretos (incluindo vínculos aluno-responsável).
- `student_create` integra com `StudentService` para criar aluno.
- `student_create` propaga erros de validação de volta ao form.
Ver Sprint 03 §96-103.
"""

import pytest


@pytest.fixture()
def force_login_client(client, user, db):
    client.force_login(user)
    return client


# ── Teachers ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTeacherViews:
    def _make_subject(self, code="MAT"):
        from teachers.models import Subject

        return Subject.objects.create(name="Matemática", code=code, workload=80)

    def _make_teacher(self, user, reg="MAT-001"):
        from teachers.models import Teacher

        return Teacher.objects.create(user=user, registration_number=reg)

    def test_teachers_list_requires_login(self, client):
        assert client.get("/teachers/").status_code == 302
        assert "/login/" in client.get("/teachers/")["Location"]

    def test_teachers_list_renders(self, force_login_client, user):
        self._make_teacher(user)
        resp = force_login_client.get("/teachers/")
        assert resp.status_code == 200
        assert b"MAT-001" in resp.content

    def test_teachers_list_htmx_returns_partial(self, force_login_client, user):
        self._make_teacher(user)
        resp = force_login_client.get("/teachers/", HTTP_HX_REQUEST="true")
        assert resp.status_code == 200
        # Templates no partial têm `table`, então conterá <table ...>.
        assert b"<table" in resp.content

    def test_teachers_list_filter_by_first_name(self, force_login_client, user):
        from core.models import CustomUser
        from teachers.models import Teacher

        # Outro professor com nome diferente
        other_user = CustomUser.objects.create_user(
            email="other-teacher@test.com",
            password="Senha123",
            first_name="Zeca",
            last_name="Silva",
        )
        Teacher.objects.create(user=other_user, registration_number="OTHER-001")

        # Professor atual (primeiro nome T)
        user.first_name = "Tiago"
        user.save()
        self._make_teacher(user, reg="MAT-001-TIAGO")

        resp = force_login_client.get("/teachers/", {"q": "Tiago"})
        assert resp.status_code == 200
        assert b"MAT-001-TIAGO" in resp.content
        assert b"OTHER-001" not in resp.content

    def test_teacher_detail_renders_with_subjects(self, force_login_client, user):
        t = self._make_teacher(user)
        math = self._make_subject()
        t.subjects.add(math)
        resp = force_login_client.get(f"/teachers/{t.pk}/")
        assert resp.status_code == 200
        assert b"Matem\xc3\xa1tica" in resp.content
        assert b"Informa\xc3\xa7\xc3\xb5es do Professor" in resp.content
        assert b"Dados Pessoais" not in resp.content
        assert b">Contato<" not in resp.content

    def test_teacher_detail_returns_404_for_unknown(self, force_login_client):
        import uuid

        resp = force_login_client.get(f"/teachers/{uuid.uuid4()}/")
        assert resp.status_code == 404


# ── Students ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestStudentViews:
    def _make(self, enrollment="SL-001"):
        from students.models import Student

        return Student.objects.create(
            first_name="Ana",
            last_name="Silva",
            birth_date="2010-01-01",
            enrollment_number=enrollment,
        )

    def test_students_list_requires_login(self, client):
        assert client.get("/students/").status_code == 302

    def test_students_list_renders(self, force_login_client):
        self._make()
        resp = force_login_client.get("/students/")
        assert resp.status_code == 200
        assert b"SL-001" in resp.content

    def test_students_filter_by_first_name(self, force_login_client):
        self._make("S-001")  # "Ana"
        from students.models import Student

        Student.objects.create(
            first_name="Bruno",
            last_name="X",
            birth_date="2010-01-01",
            enrollment_number="S-002",
        )
        resp = force_login_client.get("/students/", {"q": "Ana"})
        assert b"S-001" in resp.content
        assert b"S-002" not in resp.content

    def test_student_create_get_renders_form(self, force_login_client):
        resp = force_login_client.get("/students/novo/")
        assert resp.status_code == 200
        assert b"form" in resp.content.lower()

    def test_student_create_post_creates_student(self, force_login_client):
        resp = force_login_client.post(
            "/students/novo/",
            data={
                "first_name": "Tiago",
                "last_name": "Lima",
                "birth_date": "2010-01-01",
                "enrollment_number": "NEW-001",
                "gender": "M",
                "blood_type": "O+",
                "nationality": "Brasileira",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "rg_issuer": "SSP",
                "rg_state": "SP",
                "phone_mobile": "11999990000",
                "email": "tiago@example.com",
            },
        )
        assert resp.status_code == 302
        from students.models import Student

        assert Student.objects.filter(enrollment_number="NEW-001").exists()

    def test_student_create_post_validation_error_rerenders_form(self, force_login_client, user):
        # Matrícula duplicada
        from students.models import Student

        Student.objects.create(
            first_name="X",
            last_name="Y",
            birth_date="2010-01-01",
            enrollment_number="DUP-001",
        )
        resp = force_login_client.post(
            "/students/novo/",
            data={
                "first_name": "Outro",
                "last_name": "Aluno",
                "birth_date": "2010-01-01",
                "enrollment_number": "DUP-001",
                "gender": "NI",
            },
        )
        # Não redireciona; rerenderiza form com erro. ModelForm `validate_unique`
        # emite "Student com este Matrícula já existe." (pt-BR default).
        assert resp.status_code == 200
        assert b"j\xc3\xa1 existe" in resp.content.lower() or b"text-danger" in resp.content

    def test_student_profile_renders_with_guardians(self, force_login_client):
        from core.models import CustomUser
        from guardians.models import Guardian, StudentGuardian

        s = self._make("PRF-001")
        u = CustomUser.objects.create_user(
            email="resp@prof.test", password="Senha123", first_name="R", last_name="L"
        )
        g = Guardian.objects.create(user=u, relationship_type="PAI")
        StudentGuardian.objects.create(student=s, guardian=g, is_primary=True)

        resp = force_login_client.get(f"/students/{s.pk}/")
        assert resp.status_code == 200
        assert b"R" in resp.content
        assert b"Informa\xc3\xa7\xc3\xb5es do Aluno" in resp.content
        assert b">Documentos<" not in resp.content
        assert b">Contato<" not in resp.content

    def test_student_profile_404_when_unknown(self, force_login_client):
        import uuid

        assert force_login_client.get(f"/students/{uuid.uuid4()}/").status_code == 404


# ── Guardians ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGuardianViews:
    def _make_user(self, email="g@example.com", first="Guardian"):
        from core.models import CustomUser

        return CustomUser.objects.create_user(
            email=email, password="Senha123", first_name=first, last_name="LL"
        )

    def _make(self, email="g@example.com", rel="MAE"):
        from guardians.models import Guardian

        return Guardian.objects.create(user=self._make_user(email), relationship_type=rel)

    def test_guardians_list_requires_login(self, client):
        assert client.get("/guardians/").status_code == 302

    def test_guardians_list_renders(self, force_login_client):
        self._make()
        resp = force_login_client.get("/guardians/")
        assert resp.status_code == 302
        assert resp["Location"] == "/students/"

    def test_guardian_detail_redirects_to_students(self, force_login_client):
        from guardians.models import StudentGuardian
        from students.models import Student

        g = self._make()
        s = Student.objects.create(
            first_name="Ana",
            last_name="S",
            birth_date="2010-01-01",
            enrollment_number="DET-001",
        )
        StudentGuardian.objects.create(student=s, guardian=g)
        resp = force_login_client.get(f"/guardians/{g.pk}/")
        assert resp.status_code == 302
        assert resp["Location"] == "/students/"

    def test_guardian_detail_unknown_redirects_to_students(self, force_login_client):
        import uuid

        response = force_login_client.get(f"/guardians/{uuid.uuid4()}/")
        assert response.status_code == 302
        assert response["Location"] == "/students/"

    def test_guardian_edit_get_redirects_to_students(self, force_login_client):
        from core.models import CustomUser
        from guardians.models import Guardian

        u = CustomUser.objects.create_user(
            email="ge@test.com", password="Senha123", first_name="GE", last_name="Test"
        )
        g = Guardian.objects.create(user=u, relationship_type="PAI")
        resp = force_login_client.get(f"/guardians/{g.pk}/editar/")
        assert resp.status_code == 302
        assert resp["Location"] == "/students/"

    def test_guardian_edit_post_redirects_to_students(self, force_login_client):
        from core.models import CustomUser
        from guardians.models import Guardian

        u = CustomUser.objects.create_user(
            email="ge2@test.com", password="Senha123", first_name="GE2", last_name="Test"
        )
        g = Guardian.objects.create(user=u, relationship_type="PAI", phone="111")
        resp = force_login_client.post(
            f"/guardians/{g.pk}/editar/",
            {
                "first_name": "GE2",
                "last_name": "Test",
                "relationship_type": "MAE",
                "birth_date": "1980-01-01",
                "gender": "M",
                "nationality": "Brasileira",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "rg_issuer": "SSP",
                "rg_state": "SP",
                "phone": "999",
                "phone_whatsapp": "11999991111",
                "phone_mobile": "11988882222",
            },
        )
        assert resp.status_code == 302
        assert resp["Location"] == "/students/"

    def test_teacher_edit_get_redirects_to_profile(self, force_login_client, user):
        from teachers.models import Teacher

        t = Teacher.objects.create(
            user=user, registration_number="EDT001", created_by=user, updated_by=user
        )
        resp = force_login_client.get(f"/teachers/{t.pk}/editar/")
        assert resp.status_code == 302
        assert resp["Location"] == f"/teachers/{t.pk}/"

    def test_teacher_edit_post_updates(self, force_login_client, user):
        from teachers.models import Teacher

        t = Teacher.objects.create(
            user=user, registration_number="EDT002", created_by=user, updated_by=user
        )
        resp = force_login_client.post(
            f"/teachers/{t.pk}/editar/",
            {
                "registration_number": "EDT002",
                "hire_date": "2025-06-15",
                "birth_date": "1990-05-20",
                "gender": "M",
                "nationality": "Brasileira",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "rg_issuer": "SSP",
                "rg_state": "SP",
                "phone_mobile": "11999999999",
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        )
        assert resp.status_code == 302
        t.refresh_from_db()
        assert str(t.hire_date) == "2025-06-15"
        assert t.phone_mobile == "11999999999"

    def test_student_edit_get_redirects_to_profile(self, force_login_client):
        from students.models import Student

        s = Student.objects.create(
            first_name="Edit",
            last_name="Test",
            birth_date="2010-01-01",
            enrollment_number="EDT-STU",
        )
        resp = force_login_client.get(f"/students/{s.pk}/editar/")
        assert resp.status_code == 302
        assert resp["Location"] == f"/students/{s.pk}/"
