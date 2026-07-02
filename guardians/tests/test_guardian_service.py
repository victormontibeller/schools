"""Testes do GuardianService."""

import pytest

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from core.models import CustomUser
from guardians.models import StudentGuardian
from guardians.services import GuardianService
from students.services import StudentService


def _make_user(email):
    return CustomUser.objects.create_user(
        email=email, password="Senha123", first_name="Test", last_name="User"
    )


def _make_student(user, enrollment):
    return StudentService(user=user).create_student(
        {
            "first_name": "Aluno",
            "last_name": "Teste",
            "birth_date": "2010-01-01",
            "enrollment_number": enrollment,
        }
    )


@pytest.mark.django_db
class TestCreateGuardian:
    def test_success(self, user):
        target = _make_user("resp@test.com")
        g = GuardianService(user=user).create_guardian(
            {
                "user_id": target.pk,
                "relationship_type": "MAE",
            }
        )
        assert g.pk is not None
        assert g.relationship_type == "MAE"

    def test_duplicate_user(self, user):
        target = _make_user("resp2@test.com")
        GuardianService(user=user).create_guardian(
            {"user_id": target.pk, "relationship_type": "PAI"}
        )
        with pytest.raises(BusinessRuleViolationError):
            GuardianService(user=user).create_guardian(
                {"user_id": target.pk, "relationship_type": "MAE"}
            )

    def test_missing_relationship(self, user):
        target = _make_user("resp3@test.com")
        with pytest.raises(ValidationError):
            GuardianService(user=user).create_guardian(
                {"user_id": target.pk, "relationship_type": ""}
            )

    def test_user_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            GuardianService(user=user).create_guardian(
                {"user_id": uuid.uuid4(), "relationship_type": "MAE"}
            )


@pytest.mark.django_db
class TestLinkStudent:
    def test_link_success(self, user):
        guardian_user = _make_user("g_link@test.com")
        g = GuardianService(user=user).create_guardian(
            {"user_id": guardian_user.pk, "relationship_type": "PAI"}
        )
        student = _make_student(user, "LNK001")
        link = GuardianService(user=user).link_student(g.pk, student.pk, {"is_primary": True})
        assert link.is_primary is True
        assert StudentGuardian.objects.filter(guardian=g, student=student).exists()

    def test_duplicate_link(self, user):
        guardian_user = _make_user("g_dup@test.com")
        g = GuardianService(user=user).create_guardian(
            {"user_id": guardian_user.pk, "relationship_type": "MAE"}
        )
        student = _make_student(user, "DUP001")
        GuardianService(user=user).link_student(g.pk, student.pk)
        with pytest.raises(BusinessRuleViolationError):
            GuardianService(user=user).link_student(g.pk, student.pk)

    def test_multiple_primaries_allowed(self, user):
        g1_user = _make_user("g1p@test.com")
        g2_user = _make_user("g2p@test.com")
        g1 = GuardianService(user=user).create_guardian(
            {"user_id": g1_user.pk, "relationship_type": "PAI"}
        )
        g2 = GuardianService(user=user).create_guardian(
            {"user_id": g2_user.pk, "relationship_type": "MAE"}
        )
        student = _make_student(user, "PRM001")
        GuardianService(user=user).link_student(g1.pk, student.pk, {"is_primary": True})
        GuardianService(user=user).link_student(g2.pk, student.pk, {"is_primary": True})
        assert StudentGuardian.objects.filter(student=student, is_primary=True).count() == 2

    def test_unlink_student(self, user):
        g_user = _make_user("g_ul@test.com")
        g = GuardianService(user=user).create_guardian(
            {"user_id": g_user.pk, "relationship_type": "MAE"}
        )
        student = _make_student(user, "UNL001")
        GuardianService(user=user).link_student(g.pk, student.pk)
        GuardianService(user=user).unlink_student(g.pk, student.pk)
        assert not StudentGuardian.objects.filter(guardian=g, student=student).exists()

    def test_unlink_not_found(self, user):
        g_user = _make_user("g_unf@test.com")
        g = GuardianService(user=user).create_guardian(
            {"user_id": g_user.pk, "relationship_type": "MAE"}
        )
        student = _make_student(user, "UNF001")
        with pytest.raises(ObjectNotFoundError):
            GuardianService(user=user).unlink_student(g.pk, student.pk)

    def test_link_student_not_found(self, user):
        import uuid

        g_user = _make_user("g_snf@test.com")
        g = GuardianService(user=user).create_guardian(
            {"user_id": g_user.pk, "relationship_type": "MAE"}
        )
        with pytest.raises(ObjectNotFoundError):
            GuardianService(user=user).link_student(g.pk, uuid.uuid4())


@pytest.mark.django_db
class TestUpdateGuardian:
    def test_success(self, user):
        g_user = _make_user("g_upd@test.com")
        g = GuardianService(user=user).create_guardian(
            {"user_id": g_user.pk, "relationship_type": "MAE"}
        )
        updated = GuardianService(user=user).update_guardian(
            g.pk, {"relationship_type": "PAI", "phone": "123456789"}
        )
        assert updated.relationship_type == "PAI"
        assert updated.phone == "123456789"


@pytest.mark.django_db
class TestCreateGuardianEdgeCases:
    def test_missing_user_id(self, user):
        with pytest.raises(ValidationError):
            GuardianService(user=user).create_guardian({"relationship_type": "MAE"})
