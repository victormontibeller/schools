"""Testes do StudentService."""

import pytest

from base.exceptions import BusinessRuleViolationError, ValidationError
from students.services import StudentService

_BASE_DATA = {
    "first_name": "Maria",
    "last_name": "Souza",
    "birth_date": "2010-05-15",
    "enrollment_number": "2024001",
    "gender": "F",
    "blood_type": "O+",
    "nationality": "Brasileira",
    "cpf": "390.533.447-05",
    "rg_number": "1234567",
    "rg_issuer": "SSP",
    "rg_state": "SP",
    "phone_mobile": "11999990000",
    "email": "maria@example.com",
}


@pytest.mark.django_db
class TestCreateStudent:
    def test_success(self, user):
        s = StudentService(user=user).create_student(_BASE_DATA)
        assert s.pk is not None
        assert s.enrollment_number == "2024001"

    def test_duplicate_enrollment(self, user):
        StudentService(user=user).create_student(_BASE_DATA)
        with pytest.raises(ValidationError):
            StudentService(user=user).create_student(_BASE_DATA)

    def test_missing_required_fields(self, user):
        with pytest.raises(ValidationError):
            StudentService(user=user).create_student({"first_name": "Sem"})


@pytest.mark.django_db
class TestUpdateStudent:
    def test_update_succeeds_with_partial_data(self, user):
        student = StudentService(user=user).create_student(
            {**_BASE_DATA, "enrollment_number": "PARTIAL-001"}
        )

        updated = StudentService(user=user).update_student(student.pk, {"first_name": "Ana"})

        assert updated.first_name == "Ana"
        assert updated.last_name == _BASE_DATA["last_name"]

    def test_success(self, user):
        s = StudentService(user=user).create_student({**_BASE_DATA, "enrollment_number": "UPD001"})
        updated = StudentService(user=user).update_student(
            s.pk,
            {**_BASE_DATA, "enrollment_number": "UPD001", "first_name": "Ana"},
        )
        assert updated.first_name == "Ana"
        assert updated.version == 1

    def test_update_records_old_values_for_audit(self, user):
        from audit.models import AuditLog

        s = StudentService(user=user).create_student(
            {**_BASE_DATA, "enrollment_number": "AUD-STU", "email": "student-audit@test.com"}
        )

        StudentService(user=user).update_student(
            s.pk,
            {
                **_BASE_DATA,
                "enrollment_number": "AUD-STU",
                "first_name": "Ana",
                "cpf": "529.982.247-25",
                "email": "student-updated@test.com",
            },
        )

        log = AuditLog.objects.filter(
            operation=AuditLog.Operation.UPDATE,
            model_name="Student",
            object_id=str(s.pk),
        ).latest("created_at")
        assert log.old_values["first_name"] == "[REDACTED]"
        assert log.old_values["cpf"] == "[REDACTED]"
        assert log.old_values["email"] == "[REDACTED]"

    def test_duplicate_enrollment_on_update(self, user):
        StudentService(user=user).create_student({**_BASE_DATA, "enrollment_number": "E001"})
        s2 = StudentService(user=user).create_student(
            {
                **_BASE_DATA,
                "enrollment_number": "E002",
                "first_name": "João",
                "cpf": "529.982.247-25",
                "email": "joao@example.com",
            }
        )
        with pytest.raises(ValidationError):
            StudentService(user=user).update_student(
                s2.pk,
                {
                    **_BASE_DATA,
                    "enrollment_number": "E001",
                    "first_name": "João",
                    "cpf": "529.982.247-25",
                    "email": "joao@example.com",
                },
            )


@pytest.mark.django_db
class TestDeactivateRestoreStudent:
    def test_deactivate(self, user):
        s = StudentService(user=user).create_student({**_BASE_DATA, "enrollment_number": "D001"})
        StudentService(user=user).deactivate_student(s.pk)
        s.refresh_from_db()
        assert s.deleted_at is not None

    def test_restore(self, user):
        s = StudentService(user=user).create_student({**_BASE_DATA, "enrollment_number": "R001"})
        StudentService(user=user).deactivate_student(s.pk)
        StudentService(user=user).restore_student(s.pk)
        s.refresh_from_db()
        assert s.deleted_at is None

    def test_deactivate_already_deleted(self, user):
        s = StudentService(user=user).create_student({**_BASE_DATA, "enrollment_number": "DD001"})
        StudentService(user=user).deactivate_student(s.pk)
        with pytest.raises(BusinessRuleViolationError):
            StudentService(user=user).deactivate_student(s.pk)
