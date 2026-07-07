"""Testes do TeacherService."""

import datetime as dt

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from core.models import CustomUser
from teachers.models import Subject
from teachers.services import TeacherService


def _make_user(email="teacher@test.com"):
    return CustomUser.objects.create_user(
        email=email, password="Senha123", first_name="João", last_name="Silva"
    )


@pytest.mark.django_db
class TestCreateTeacher:
    def test_success(self, user):
        target = _make_user()
        t = TeacherService(user=user).create_teacher(
            {"user_id": target.pk, "registration_number": "MAT-001"}
        )
        assert t.pk is not None
        assert t.registration_number == "MAT-001"

    def test_duplicate_user(self, user):
        target = _make_user("dup@test.com")
        TeacherService(user=user).create_teacher(
            {"user_id": target.pk, "registration_number": "MAT-002"}
        )
        with pytest.raises(BusinessRuleViolationError):
            TeacherService(user=user).create_teacher(
                {"user_id": target.pk, "registration_number": "MAT-003"}
            )

    def test_duplicate_registration(self, user):
        u1 = _make_user("u1@test.com")
        u2 = _make_user("u2@test.com")
        TeacherService(user=user).create_teacher({"user_id": u1.pk, "registration_number": "MAT-X"})
        with pytest.raises(ValidationError):
            TeacherService(user=user).create_teacher(
                {"user_id": u2.pk, "registration_number": "MAT-X"}
            )

    def test_missing_registration(self, user):
        target = _make_user("nomat@test.com")
        with pytest.raises(ValidationError):
            TeacherService(user=user).create_teacher(
                {"user_id": target.pk, "registration_number": ""}
            )

    def test_user_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            TeacherService(user=user).create_teacher(
                {"user_id": uuid.uuid4(), "registration_number": "MAT-Z"}
            )


@pytest.mark.django_db
class TestDeactivateTeacher:
    def test_success(self, user):
        target = _make_user("deact@test.com")
        teacher = TeacherService(user=user).create_teacher(
            {"user_id": target.pk, "registration_number": "MAT-D"}
        )
        TeacherService(user=user).deactivate_teacher(teacher.pk)
        teacher.refresh_from_db()
        assert teacher.deleted_at is not None

    def test_already_deactivated(self, user):
        target = _make_user("deact2@test.com")
        teacher = TeacherService(user=user).create_teacher(
            {"user_id": target.pk, "registration_number": "MAT-D2"}
        )
        TeacherService(user=user).deactivate_teacher(teacher.pk)
        with pytest.raises(BusinessRuleViolationError):
            TeacherService(user=user).deactivate_teacher(teacher.pk)


@pytest.mark.django_db
class TestAssignSubject:
    def test_success(self, user):
        target = _make_user("subj@test.com")
        teacher = TeacherService(user=user).create_teacher(
            {"user_id": target.pk, "registration_number": "MAT-S"}
        )
        subject = Subject.objects.create(
            name="Matemática", code="MAT", created_by=user, updated_by=user
        )
        TeacherService(user=user).assign_subject(teacher.pk, subject.pk)
        assert teacher.subjects.filter(pk=subject.pk).exists()

    def test_deactivate_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            TeacherService(user=user).deactivate_teacher(uuid.uuid4())

    def test_remove_subject(self, user):
        target = _make_user("rmsubj@test.com")
        teacher = TeacherService(user=user).create_teacher(
            {"user_id": target.pk, "registration_number": "MAT-RM"}
        )
        subject = Subject.objects.create(
            name="Física", code="FIS", created_by=user, updated_by=user
        )
        TeacherService(user=user).assign_subject(teacher.pk, subject.pk)
        TeacherService(user=user).remove_subject(teacher.pk, subject.pk)
        assert not teacher.subjects.filter(pk=subject.pk).exists()

    def test_update_teacher(self, user):
        target = _make_user("updtch@test.com")
        teacher = TeacherService(user=user).create_teacher(
            {"user_id": target.pk, "registration_number": "MAT-UP"}
        )
        avatar = SimpleUploadedFile(
            "avatar.gif",
            (
                b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
                b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00"
                b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
            ),
            content_type="image/gif",
        )
        updated = TeacherService(user=user).update_teacher(
            teacher.pk,
            {
                "first_name": "Marina",
                "last_name": "Oliveira",
                "registration_number": "MAT-UP2",
                "hire_date": dt.date(2025, 1, 15),
                "birth_date": dt.date(1992, 4, 10),
                "gender": "F",
                "nationality": "Brasileira",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "rg_issuer": "SSP",
                "rg_state": "SP",
                "phone_mobile": "(11) 99999-0000",
                "avatar": avatar,
            },
        )
        updated.refresh_from_db()
        updated.user.refresh_from_db()
        assert updated.hire_date == dt.date(2025, 1, 15)
        assert updated.registration_number == "MAT-UP2"
        assert updated.user.first_name == "Marina"
        assert updated.user.last_name == "Oliveira"
        assert updated.user.avatar.name.endswith(".gif")
        assert "avatar" in updated.user.avatar.name

    def test_duplicate_assignment(self, user):
        target = _make_user("subj2@test.com")
        teacher = TeacherService(user=user).create_teacher(
            {"user_id": target.pk, "registration_number": "MAT-S2"}
        )
        subject = Subject.objects.create(
            name="Física", code="FIS", created_by=user, updated_by=user
        )
        TeacherService(user=user).assign_subject(teacher.pk, subject.pk)
        with pytest.raises(BusinessRuleViolationError):
            TeacherService(user=user).assign_subject(teacher.pk, subject.pk)

    def test_set_subjects_replaces_current_links(self, user):
        target = _make_user("syncsubj@test.com")
        teacher = TeacherService(user=user).create_teacher(
            {"user_id": target.pk, "registration_number": "MAT-SYNC"}
        )
        first = Subject.objects.create(
            name="Matemática", code="MAT-SYNC", created_by=user, updated_by=user
        )
        second = Subject.objects.create(
            name="História", code="HIS-SYNC", created_by=user, updated_by=user
        )
        teacher.subjects.add(first)

        TeacherService(user=user).set_subjects(teacher.pk, [second])

        assert list(teacher.subjects.values_list("pk", flat=True)) == [second.pk]


@pytest.mark.django_db
class TestSubjectServiceUpdate:
    def test_update_subject_name(self, user):
        from teachers.models import Subject
        from teachers.services import SubjectService

        s = Subject.objects.create(name="Original", code="ORG", created_by=user, updated_by=user)
        result = SubjectService(user=user).update_subject(s.pk, {"name": "Novo Nome"})
        assert result.name == "Novo Nome"

    def test_update_subject_code_duplicate(self, user):
        from teachers.models import Subject
        from teachers.services import SubjectService

        s1 = Subject.objects.create(name="A", code="AAA", created_by=user, updated_by=user)
        Subject.objects.create(name="B", code="BBB", created_by=user, updated_by=user)
        with pytest.raises(ValidationError):
            SubjectService(user=user).update_subject(s1.pk, {"code": "BBB"})
