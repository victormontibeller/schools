"""Testes do StudentService."""

import pytest

from base.exceptions import BusinessRuleViolationError, ValidationError
from students.services import StudentService

_BASE_DATA = {
    "first_name": "Maria",
    "last_name": "Souza",
    "birth_date": "2010-05-15",
    "enrollment_number": "2024001",
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
    def test_success(self, user):
        s = StudentService(user=user).create_student({**_BASE_DATA, "enrollment_number": "UPD001"})
        updated = StudentService(user=user).update_student(s.pk, {"first_name": "Ana"})
        assert updated.first_name == "Ana"
        assert updated.version == 1

    def test_update_records_old_values_for_audit(self, user):
        from audit.models import AuditLog

        s = StudentService(user=user).create_student(
            {
                **_BASE_DATA,
                "enrollment_number": "AUD-STU",
                "cpf": "390.533.447-05",
                "rg_state": "SP",
                "email": "student-audit@test.com",
            }
        )

        StudentService(user=user).update_student(
            s.pk,
            {
                "first_name": "Ana",
                "cpf": "529.982.247-25",
                "rg_state": "RJ",
                "email": "student-updated@test.com",
            },
        )

        log = AuditLog.objects.filter(
            operation=AuditLog.Operation.UPDATE,
            model_name="Student",
            object_id=str(s.pk),
        ).latest("created_at")
        assert log.old_values["first_name"] == "Maria"
        assert log.old_values["cpf"] == "39053344705"
        assert log.old_values["rg_state"] == "SP"
        assert log.old_values["email"] == "student-audit@test.com"

    def test_duplicate_enrollment_on_update(self, user):
        StudentService(user=user).create_student({**_BASE_DATA, "enrollment_number": "E001"})
        s2 = StudentService(user=user).create_student(
            {**_BASE_DATA, "enrollment_number": "E002", "first_name": "João"}
        )
        with pytest.raises(ValidationError):
            StudentService(user=user).update_student(s2.pk, {"enrollment_number": "E001"})


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
