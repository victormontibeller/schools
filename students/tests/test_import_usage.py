"""Selo transacional, rollback e recuperação explícita da carga assistida."""

from unittest.mock import patch

import pytest

from base.exceptions import BusinessRuleViolationError
from guardians.models import Guardian, StudentGuardian
from guardians.services import GuardianService
from students.import_services import AssistedImportService
from students.import_usage_services import ImportUsageService
from students.models import Student
from students.services import StudentService
from students.tests.test_assisted_import import files

pytestmark = pytest.mark.django_db


@pytest.fixture
def imported(user):
    batch = AssistedImportService(user=user).import_batch("usage", files())
    return batch, Student.objects.get(), Guardian.objects.get()


def test_update_seals_batch_and_undo_refuses_even_after_edit_reverted(user, imported):
    batch, student, _ = imported
    StudentService(user=user).update_student(student.pk, {"first_name": "Revisado"})
    batch.refresh_from_db()
    assert batch.status == "SEALED"
    with pytest.raises(BusinessRuleViolationError):
        AssistedImportService(user=user).deactivate_batch(batch.pk)


def test_failed_operational_audit_rolls_back_seal_and_changes(user, imported):
    batch, student, _ = imported
    with patch.object(StudentService, "_record_audit", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            StudentService(user=user).update_student(student.pk, {"first_name": "Revisado"})
    batch.refresh_from_db()
    assert batch.status == "IMPORTED"
    AssistedImportService(user=user).deactivate_batch(batch.pk)


def test_reverted_roots_reject_stale_usage_and_individual_restore(user, imported):
    batch, student, guardian = imported
    AssistedImportService(user=user).deactivate_batch(batch.pk)
    for operation in (
        lambda: ImportUsageService(user=user).seal_for_use(student_ids=[student.pk]),
        lambda: StudentService(user=user).restore_student(student.pk),
        lambda: GuardianService(user=user).link_student(guardian.pk, student.pk, {}),
    ):
        with pytest.raises(BusinessRuleViolationError):
            operation()
    assert not Student.objects.exists()


def test_restore_batch_recovers_same_ids_for_audited_correction(user, imported):
    batch, student, guardian = imported
    service = AssistedImportService(user=user)
    service.deactivate_batch(batch.pk)
    restored = service.restore_batch(batch.pk)
    assert restored.status == "SEALED"
    assert Student.objects.get().pk == student.pk
    assert Guardian.objects.get().pk == guardian.pk
    assert StudentGuardian.objects.count() == 1
    StudentService(user=user).update_student(student.pk, {"first_name": "Conferido"})
    assert Student.objects.get().first_name == "Conferido"
    with pytest.raises(BusinessRuleViolationError):
        service.deactivate_batch(batch.pk)


def test_restore_batch_audit_failure_keeps_all_records_reverted(user, imported):
    batch, _, _ = imported
    service = AssistedImportService(user=user)
    service.deactivate_batch(batch.pk)
    with patch.object(service, "_record_audit", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            service.restore_batch(batch.pk)
    batch.refresh_from_db()
    assert batch.status == "REVERTED"
    assert not Student.objects.exists()
    assert not Guardian.objects.exists()


def test_seal_does_not_lock_batches_or_administrators_for_unimported_roots(user):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    student = Student.objects.create(
        first_name="Sem carga", last_name="Fictício", birth_date="2022-01-01"
    )
    with CaptureQueriesContext(connection) as queries:
        ImportUsageService(user=user).seal_for_use(student_ids=[student.pk])
    assert not any("core_role" in row["sql"] for row in queries)
    assert not any("students_assistedimportbatch" in row["sql"] for row in queries)


def test_restore_batch_refuses_replacement_identity_without_partial_restore(user, imported):
    batch, _, guardian = imported
    service = AssistedImportService(user=user)
    service.deactivate_batch(batch.pk)
    from students.import_validation import parse_import

    GuardianService(user=user).create_guardian(parse_import(files())["guardians"][0])
    with pytest.raises(BusinessRuleViolationError, match="cadastro substituto"):
        service.restore_batch(batch.pk)
    assert not Student.objects.exists()
    assert not StudentGuardian.objects.exists()
    assert Guardian.objects.count() == 1
    batch.refresh_from_db()
    assert batch.status == "REVERTED"
