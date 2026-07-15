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


def _guardian_data(user_id, _relationship_type="MAE", *, cpf="390.533.447-05"):
    suffix = str(user_id or "contact")[:8]
    return {
        "first_name": "Contato",
        "last_name": suffix,
        "email": f"contato-{suffix}@test.com",
        "birth_date": "1980-01-01",
        "gender": "F",
        "nationality": "Brasileira",
        "cpf": cpf,
        "rg_number": "1234567",
        "rg_issuer": "SSP",
        "rg_state": "SP",
        "phone": "1133334444",
        "phone_whatsapp": "11999991111",
        "phone_mobile": "11988882222",
    }


def _make_student(user, enrollment):
    return StudentService(user=user).create_student(
        {
            "first_name": "Aluno",
            "last_name": "Teste",
            "birth_date": "2010-01-01",
            "enrollment_number": enrollment,
            "gender": "M",
            "blood_type": "O+",
            "nationality": "Brasileira",
            "cpf": "529.982.247-25",
            "rg_number": "7654321",
            "rg_issuer": "SSP",
            "rg_state": "SP",
            "phone_mobile": "11977773333",
            "email": "aluno@example.com",
        }
    )


@pytest.mark.django_db
class TestCreateGuardian:
    def test_create_succeeds_without_user(self, user):
        guardian = GuardianService(user=user).create_guardian(
            {
                **_guardian_data(None),
                "first_name": "Contato",
                "last_name": "Sem Login",
                "email": "contato@test.com",
            }
        )

        assert guardian.user is None
        assert guardian.full_name == "Contato Sem Login"

    def test_success(self, user):
        target = _make_user("resp@test.com")
        g = GuardianService(user=user).create_guardian(_guardian_data(target.pk))
        assert g.pk is not None
        assert g.user is None

    def test_duplicate_cpf(self, user):
        target = _make_user("resp2@test.com")
        GuardianService(user=user).create_guardian(_guardian_data(target.pk, "PAI"))
        with pytest.raises(ValidationError):
            GuardianService(user=user).create_guardian(_guardian_data(target.pk))

    def test_missing_name(self, user):
        with pytest.raises(ValidationError):
            GuardianService(user=user).create_guardian({"first_name": "", "last_name": ""})

    def test_unknown_extra_field_does_not_link_account(self, user):
        import uuid

        guardian = GuardianService(user=user).create_guardian(_guardian_data(uuid.uuid4()))
        assert guardian.user is None


@pytest.mark.django_db
class TestLinkStudent:
    def test_create_and_link_succeeds_without_user(self, user):
        student = _make_student(user, "NEW-LINK")
        link = GuardianService(user=user).create_and_link_student(
            student.pk,
            {
                **_guardian_data(None),
                "first_name": "Contato",
                "last_name": "Novo",
                "email": "contato.novo@test.com",
            },
            {"relationship_type": "MAE", "is_primary": True},
        )

        assert link.student_id == student.pk
        assert link.guardian.user is None
        assert link.relationship_type == "MAE"

    def test_link_success(self, user):
        guardian_user = _make_user("g_link@test.com")
        g = GuardianService(user=user).create_guardian(_guardian_data(guardian_user.pk, "PAI"))
        student = _make_student(user, "LNK001")
        link = GuardianService(user=user).link_student(g.pk, student.pk, {"is_primary": True})
        assert link.is_primary is True
        assert StudentGuardian.objects.filter(guardian=g, student=student).exists()

    def test_duplicate_link(self, user):
        guardian_user = _make_user("g_dup@test.com")
        g = GuardianService(user=user).create_guardian(_guardian_data(guardian_user.pk))
        student = _make_student(user, "DUP001")
        GuardianService(user=user).link_student(g.pk, student.pk)
        with pytest.raises(BusinessRuleViolationError):
            GuardianService(user=user).link_student(g.pk, student.pk)

    def test_link_replaces_existing_primary(self, user):
        g1_user = _make_user("g1p@test.com")
        g2_user = _make_user("g2p@test.com")
        g1 = GuardianService(user=user).create_guardian(_guardian_data(g1_user.pk, "PAI"))
        g2 = GuardianService(user=user).create_guardian(
            _guardian_data(g2_user.pk, cpf="529.982.247-25")
        )
        student = _make_student(user, "PRM001")
        GuardianService(user=user).link_student(g1.pk, student.pk, {"is_primary": True})
        GuardianService(user=user).link_student(g2.pk, student.pk, {"is_primary": True})
        assert StudentGuardian.objects.filter(student=student, is_primary=True).count() == 1
        assert StudentGuardian.objects.get(guardian=g2, student=student).is_primary is True

    def test_unlink_student(self, user):
        g_user = _make_user("g_ul@test.com")
        g = GuardianService(user=user).create_guardian(_guardian_data(g_user.pk))
        student = _make_student(user, "UNL001")
        GuardianService(user=user).link_student(g.pk, student.pk)
        GuardianService(user=user).unlink_student(g.pk, student.pk)
        assert not StudentGuardian.objects.filter(guardian=g, student=student).exists()

    def test_unlink_not_found(self, user):
        g_user = _make_user("g_unf@test.com")
        g = GuardianService(user=user).create_guardian(_guardian_data(g_user.pk))
        student = _make_student(user, "UNF001")
        with pytest.raises(ObjectNotFoundError):
            GuardianService(user=user).unlink_student(g.pk, student.pk)

    def test_link_student_not_found(self, user):
        import uuid

        g_user = _make_user("g_snf@test.com")
        g = GuardianService(user=user).create_guardian(_guardian_data(g_user.pk))
        with pytest.raises(ObjectNotFoundError):
            GuardianService(user=user).link_student(g.pk, uuid.uuid4())


@pytest.mark.django_db
class TestUpdateGuardian:
    def test_success(self, user):
        g_user = _make_user("g_upd@test.com")
        g = GuardianService(user=user).create_guardian(_guardian_data(g_user.pk))
        updated = GuardianService(user=user).update_guardian(
            g.pk,
            {
                "first_name": "Test",
                "last_name": "Updated",
                "email": "g_upd@test.com",
                "relationship_type": "PAI",
                "birth_date": "1980-01-01",
                "gender": "M",
                "nationality": "Brasileiro",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "rg_issuer": "SSP",
                "rg_state": "SP",
                "phone": "123456789",
                "phone_whatsapp": "11999999999",
                "phone_mobile": "11988888888",
            },
        )
        assert updated.phone == "1133334444"
        assert updated.last_name == "Updated"


@pytest.mark.django_db
class TestCreateGuardianEdgeCases:
    def test_user_id_is_not_required(self, user):
        guardian = GuardianService(user=user).create_guardian(_guardian_data(None))
        assert guardian.user is None
