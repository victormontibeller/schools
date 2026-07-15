"""Testes do TeacherService."""

import datetime as dt

import pytest

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.tests.images import png_upload
from core.models import CustomUser
from teachers.models import Subject
from teachers.services import TeacherService


def _make_user(email="teacher@test.com"):
    return CustomUser.objects.create_user(
        email=email, password="Senha123", first_name="João", last_name="Silva"
    )


def _teacher_data(user_id, registration_number, *, cpf="390.533.447-05"):
    target = CustomUser.objects.get(pk=user_id)
    return {
        "first_name": target.first_name,
        "last_name": target.last_name,
        "email": target.email,
        "registration_number": registration_number,
        "hire_date": dt.date(2020, 1, 15),
        "birth_date": dt.date(1990, 5, 20),
        "gender": "M",
        "nationality": "Brasileira",
        "cpf": cpf,
        "rg_number": "1234567",
        "rg_issuer": "SSP",
        "rg_state": "SP",
        "phone_mobile": "11999990000",
    }


@pytest.mark.django_db
class TestCreateTeacher:
    def test_success(self, user):
        target = _make_user()
        t = TeacherService(user=user).create_teacher(_teacher_data(target.pk, "MAT-001"))
        assert t.pk is not None
        assert t.registration_number.startswith("PRO-")

    def test_generates_sequential_registration_and_default_consent(self, user):
        first = TeacherService(user=user).create_teacher(
            _teacher_data(_make_user("sequence-1@test.com").pk, "IGNORED-1")
        )
        second = TeacherService(user=user).create_teacher(
            _teacher_data(
                _make_user("sequence-2@test.com").pk,
                "IGNORED-2",
                cpf="529.982.247-25",
            )
        )
        assert first.registration_number < second.registration_number
        assert first.accepts_email_notifications is False
        assert first.accepts_whatsapp_notifications is False

    def test_duplicate_user(self, user):
        target = _make_user("dup@test.com")
        TeacherService(user=user).create_teacher(_teacher_data(target.pk, "MAT-002"))
        with pytest.raises(BusinessRuleViolationError):
            TeacherService(user=user).create_teacher(_teacher_data(target.pk, "MAT-003"))

    def test_ignores_supplied_registration(self, user):
        u1 = _make_user("u1@test.com")
        u2 = _make_user("u2@test.com")
        TeacherService(user=user).create_teacher(_teacher_data(u1.pk, "MAT-X"))
        second = TeacherService(user=user).create_teacher(
            _teacher_data(u2.pk, "MAT-X", cpf="529.982.247-25")
        )
        assert second.registration_number != "MAT-X"

    def test_missing_registration_is_generated(self, user):
        target = _make_user("nomat@test.com")
        teacher = TeacherService(user=user).create_teacher(_teacher_data(target.pk, ""))
        assert teacher.registration_number.startswith("PRO-")

    def test_missing_identity_is_rejected(self, user):
        with pytest.raises(ValidationError):
            TeacherService(user=user).create_teacher({"hire_date": dt.date(2020, 1, 15)})


@pytest.mark.django_db
class TestDeactivateTeacher:
    def test_success(self, user):
        target = _make_user("deact@test.com")
        teacher = TeacherService(user=user).create_teacher(_teacher_data(target.pk, "MAT-D"))
        TeacherService(user=user).deactivate_teacher(teacher.pk)
        teacher.refresh_from_db()
        assert teacher.deleted_at is not None

    def test_already_deactivated(self, user):
        target = _make_user("deact2@test.com")
        teacher = TeacherService(user=user).create_teacher(_teacher_data(target.pk, "MAT-D2"))
        TeacherService(user=user).deactivate_teacher(teacher.pk)
        with pytest.raises(BusinessRuleViolationError):
            TeacherService(user=user).deactivate_teacher(teacher.pk)


@pytest.mark.django_db
class TestAssignSubject:
    def test_success(self, user):
        from audit.models import AuditLog

        target = _make_user("subj@test.com")
        teacher = TeacherService(user=user).create_teacher(_teacher_data(target.pk, "MAT-S"))
        subject = Subject.objects.create(
            name="Matemática", code="MAT", created_by=user, updated_by=user
        )
        TeacherService(user=user).assign_subject(teacher.pk, subject.pk)
        assert teacher.subjects.filter(pk=subject.pk).exists()
        log = AuditLog.objects.filter(
            operation=AuditLog.Operation.UPDATE,
            model_name="Teacher",
            object_id=str(teacher.pk),
        ).latest("created_at")
        assert log.old_values == {"subject_ids": []}
        assert log.new_values == {"subject_ids": [str(subject.pk)]}

    def test_deactivate_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            TeacherService(user=user).deactivate_teacher(uuid.uuid4())

    def test_remove_subject(self, user):
        target = _make_user("rmsubj@test.com")
        teacher = TeacherService(user=user).create_teacher(_teacher_data(target.pk, "MAT-RM"))
        subject = Subject.objects.create(
            name="Física", code="FIS", created_by=user, updated_by=user
        )
        TeacherService(user=user).assign_subject(teacher.pk, subject.pk)
        TeacherService(user=user).remove_subject(teacher.pk, subject.pk)
        assert not teacher.subjects.filter(pk=subject.pk).exists()

    def test_update_teacher(self, user):
        target = _make_user("updtch@test.com")
        teacher = TeacherService(user=user).create_teacher(_teacher_data(target.pk, "MAT-UP"))
        avatar = png_upload()
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
        assert updated.registration_number == teacher.registration_number
        assert updated.user.first_name == "Marina"
        assert updated.user.last_name == "Oliveira"
        assert updated.user.avatar.name.endswith(".png")
        assert "avatar" in updated.user.avatar.name

    def test_duplicate_assignment(self, user):
        target = _make_user("subj2@test.com")
        teacher = TeacherService(user=user).create_teacher(_teacher_data(target.pk, "MAT-S2"))
        subject = Subject.objects.create(
            name="Física", code="FIS", created_by=user, updated_by=user
        )
        TeacherService(user=user).assign_subject(teacher.pk, subject.pk)
        with pytest.raises(BusinessRuleViolationError):
            TeacherService(user=user).assign_subject(teacher.pk, subject.pk)

    def test_set_subjects_replaces_current_links(self, user):
        from audit.models import AuditLog

        target = _make_user("syncsubj@test.com")
        teacher = TeacherService(user=user).create_teacher(_teacher_data(target.pk, "MAT-SYNC"))
        first = Subject.objects.create(
            name="Matemática", code="MAT-SYNC", created_by=user, updated_by=user
        )
        second = Subject.objects.create(
            name="História", code="HIS-SYNC", created_by=user, updated_by=user
        )
        teacher.subjects.add(first)

        TeacherService(user=user).set_subjects(teacher.pk, [second])

        assert list(teacher.subjects.values_list("pk", flat=True)) == [second.pk]
        log = AuditLog.objects.filter(
            operation=AuditLog.Operation.UPDATE,
            model_name="Teacher",
            object_id=str(teacher.pk),
        ).latest("created_at")
        assert log.old_values == {"subject_ids": [str(first.pk)]}
        assert log.new_values == {"subject_ids": [str(second.pk)]}


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
