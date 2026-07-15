"""Testes dos selectors de professores, alunos e responsáveis.

Cobrem consultas paginadas, busca por ID (com ObjectNotFoundError) e lookup
por campo único (enrollment, email) — ver Sprint 03 §46-50 e §68-71.
"""

import pytest

from base.exceptions import ObjectNotFoundError


@pytest.mark.django_db
class TestStudentSelector:
    def _make(self, enrollment, first="Ana"):
        from students.models import Student

        return Student.objects.create(
            first_name=first,
            last_name="Silva",
            birth_date="2010-01-01",
            enrollment_number=enrollment,
        )

    def test_list_returns_paginated_students(self):
        from students.selectors import StudentSelector

        for i in range(3):
            self._make(f"SL-{i:03d}")
        result = StudentSelector().list_students(page=1, page_size=2)
        assert result.total == 3
        assert len(result.items) == 2
        assert result.has_next is True
        assert result.has_previous is False

    def test_list_second_page(self):
        from students.selectors import StudentSelector

        for i in range(3):
            self._make(f"SL2-{i:03d}")
        result = StudentSelector().list_students(page=2, page_size=2)
        assert len(result.items) == 1
        assert result.has_next is False
        assert result.has_previous is True

    def test_get_student_by_id_found(self):
        from students.selectors import StudentSelector

        s = self._make("BYID-001")
        assert StudentSelector().get_student_by_id(s.pk) == s

    def test_get_student_by_id_raises_when_not_found(self):
        import uuid

        from students.selectors import StudentSelector

        with pytest.raises(ObjectNotFoundError):
            StudentSelector().get_student_by_id(uuid.uuid4())

    def test_get_student_by_enrollment_found(self):
        from students.selectors import StudentSelector

        s = self._make("ENROLL-001")
        assert StudentSelector().get_student_by_enrollment("ENROLL-001") == s

    def test_get_student_by_enrollment_returns_none_when_missing(self):
        from students.selectors import StudentSelector

        assert StudentSelector().get_student_by_enrollment("NOPE-XXX") is None


@pytest.mark.django_db
class TestTeacherSelector:
    def _make_user(self, email="t1@test.com"):
        from core.models import CustomUser

        return CustomUser.objects.create_user(
            email=email, password="Senha123", first_name="T", last_name="Last"
        )

    def _make_teacher(self, reg="MAT-001", email="t1@test.com"):
        from teachers.models import Teacher

        u = self._make_user(email)
        return Teacher.objects.create(user=u, registration_number=reg)

    def test_list_teachers_returns_one(self):
        from teachers.selectors import TeacherSelector

        self._make_teacher()
        result = TeacherSelector().list_teachers()
        assert result.total == 1
        assert result.items[0].registration_number == "MAT-001"

    def test_get_teacher_by_id_found(self):
        from teachers.selectors import TeacherSelector

        t = self._make_teacher()
        assert TeacherSelector().get_teacher_by_id(t.pk) == t

    def test_list_teacher_subjects(self):
        from teachers.models import Subject
        from teachers.selectors import TeacherSelector

        t = self._make_teacher()
        math = Subject.objects.create(name="Matemática", code="MAT", workload=80)
        t.subjects.add(math)
        subjects = TeacherSelector().list_teacher_subjects(t.pk)
        assert list(subjects) == [math]


@pytest.mark.django_db
class TestSubjectSelector:
    def _make_subject(self, code="MAT"):
        from teachers.models import Subject

        return Subject.objects.create(name="Matemática", code=code, workload=80)

    def test_list_subjects(self):
        from teachers.selectors import SubjectSelector

        self._make_subject("MAT")
        self._make_subject("POR")
        result = SubjectSelector().list_subjects()
        assert result.total == 2


@pytest.mark.django_db
class TestGuardianSelector:
    def _make_user(self, email):
        from core.models import CustomUser

        return CustomUser.objects.create_user(
            email=email, password="Senha123", first_name="G", last_name="Last"
        )

    def _make_guardian(self, email, rel="MAE"):
        from guardians.models import Guardian

        return Guardian.objects.create(user=self._make_user(email))

    def test_list_guardians(self):
        from guardians.selectors import GuardianSelector

        self._make_guardian("g1@test.com")
        self._make_guardian("g2@test.com", rel="PAI")
        result = GuardianSelector().list_guardians()
        assert result.total == 2

    def test_list_guardians_filters_by_username(self):
        from guardians.selectors import GuardianSelector

        u1 = self._make_user("abc@test.com")
        u1.first_name = "Maria"
        u1.save()
        u2 = self._make_user("xyz@test.com")
        u2.first_name = "Joana"
        u2.save()

        from guardians.models import Guardian

        Guardian.objects.create(user=u1)
        Guardian.objects.create(user=u2)

        result = GuardianSelector().list_guardians(filters={"user__first_name__icontains": "Mari"})
        assert result.total == 1


@pytest.mark.django_db
class TestAccountSelector:
    def test_get_user_by_email_found(self, user):
        from accounts.selectors import AccountSelector

        found = AccountSelector().get_user_by_email(user.email)
        assert found == user

    def test_get_user_by_email_returns_none_when_missing(self):
        from accounts.selectors import AccountSelector

        assert AccountSelector().get_user_by_email("nao@existe.com") is None

    def test_list_users_paginated(self, user):
        from accounts.selectors import AccountSelector

        result = AccountSelector().list_users()
        assert result.total == 1
        assert result.items[0] == user


@pytest.mark.django_db
def test_paginate_clamps_page_and_page_size() -> None:
    from students.models import Student
    from students.selectors import StudentSelector

    Student.objects.bulk_create(
        [
            Student(
                first_name=f"Aluno {index}",
                last_name="Teste",
                birth_date="2010-01-01",
                enrollment_number=f"PAGE-{index:03d}",
            )
            for index in range(101)
        ]
    )

    minimum = StudentSelector()._paginate(Student.objects.order_by("enrollment_number"), -3, 0)
    maximum = StudentSelector()._paginate(Student.objects.order_by("enrollment_number"), 1, 500)

    assert minimum.page == 1
    assert minimum.page_size == 1
    assert len(minimum.items) == 1
    assert maximum.page_size == 100
    assert len(maximum.items) == 100
