"""Duas ordens determinísticas da disputa reversão versus uso no PostgreSQL."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import pytest
from django.db import connections, transaction

from base.context import tenant_schema_context
from base.exceptions import BusinessRuleViolationError
from classes.models import Class, Enrollment
from classes.services import AcademicEnrollmentService
from financeiro.models import StudentFinancialContract
from financeiro.services import FinanceService
from guardians.models import Guardian, StudentGuardian
from guardians.services import GuardianService
from notifications.tests.test_outbox_tenant import outbox_tenant as tenant_fixture
from students.import_services import AssistedImportService
from students.import_usage_services import ImportUsageService
from students.models import Student
from students.tests.test_assisted_import import files

pg_tenant = tenant_fixture

pytestmark = [
    pytest.mark.tenant,
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(os.environ.get("DJANGO_ENV") != "test_pg", reason="PostgreSQL"),
]


@pytest.mark.parametrize("kind", ["enrollment", "link", "contract"])
@pytest.mark.parametrize("undo_first", [True, False])
def test_revert_and_dependency_serialize_without_partial_results(pg_tenant, kind, undo_first):
    school, delivery = pg_tenant
    admin = delivery.recipient
    batch = AssistedImportService(user=admin).import_batch("concurrent", files())
    student = Student.objects.get(origin_import_batch=batch)
    guardian = Guardian.objects.create(first_name="Outra", last_name="Pessoa")
    cls = Class.objects.create(name="Infantil", academic_year=2026)

    def dependent():
        if kind == "enrollment":
            return AcademicEnrollmentService(user=admin).create_from_application(
                student_id=student.pk,
                class_id=cls.pk,
                academic_year=2026,
                tenant_schema=school.schema_name,
            )
        if kind == "link":
            return GuardianService(user=admin).link_student(
                guardian.pk, student.pk, {"relationship_type": "OUTRO"}
            )
        return FinanceService(user=admin).create_contract(
            {
                "student_id": student.pk,
                "academic_year": 2026,
                "name": "Contrato fictício",
                "installment_count": 1,
                "installment_value": "100.00",
                "due_day": 10,
            }
        )

    def undo():
        return AssistedImportService(user=admin).deactivate_batch(batch.pk)

    first_done, second_started, release = Event(), Event(), Event()

    def run(first):
        conn = connections["default"]
        try:
            with tenant_schema_context(school.schema_name):
                if first:
                    with transaction.atomic():
                        (undo if undo_first else dependent)()
                        first_done.set()
                        assert release.wait(15)
                else:
                    assert first_done.wait(15)
                    second_started.set()
                    try:
                        (dependent if undo_first else undo)()
                    except BusinessRuleViolationError:
                        return "denied"
                    return "unexpected-success"
                return "committed"
        finally:
            conn.close()

    with patch("notifications.outbox_services.publish_task_after_commit"):
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, True)
            second = pool.submit(run, False)
            try:
                assert first_done.wait(15)
                assert second_started.wait(15)
            finally:
                release.set()
            assert first.result(timeout=20) == "committed"
            assert second.result(timeout=20) == "denied"
    batch.refresh_from_db()
    assert batch.status == ("REVERTED" if undo_first else "SEALED")
    expected = 0 if undo_first else 1
    if kind == "enrollment":
        assert Enrollment.objects.filter(student_id=student.pk).count() == expected
    elif kind == "link":
        assert (
            StudentGuardian.objects.filter(student_id=student.pk, guardian=guardian).count()
            == expected
        )
    else:
        assert StudentFinancialContract.objects.filter(student_id=student.pk).count() == expected
    assert Student.objects.filter(pk=student.pk).exists() is not undo_first


def test_failed_dependency_releases_batch_for_reversal(pg_tenant):
    _, delivery = pg_tenant
    admin = delivery.recipient
    batch = AssistedImportService(user=admin).import_batch("rollback", files())
    student = Student.objects.get(origin_import_batch=batch)
    with pytest.raises(RuntimeError), transaction.atomic():
        ImportUsageService(user=admin).seal_for_use(student_ids=[student.pk])
        raise RuntimeError("falha após selo")
    batch.refresh_from_db()
    assert batch.status == "IMPORTED"
    AssistedImportService(user=admin).deactivate_batch(batch.pk)


@pytest.mark.parametrize("restore_first", [True, False])
def test_restore_and_replacement_guardian_enforce_unique_active_identity(pg_tenant, restore_first):
    from threading import local

    from base.exceptions import ValidationError
    from students.import_selectors import AssistedImportSelector
    from students.import_validation import parse_import

    school, delivery = pg_tenant
    admin = delivery.recipient
    batch = AssistedImportService(user=admin).import_batch("identity-race", files())
    AssistedImportService(user=admin).deactivate_batch(batch.pk)
    data = parse_import(files())["guardians"][0]
    state = local()
    first_written, second_checked, release = Event(), Event(), Event()
    original_cpf = GuardianService._validate_cpf
    original_check = AssistedImportSelector.require_uncontested_identities

    def validate_cpf(service, *args, **kwargs):
        result = original_cpf(service, *args, **kwargs)
        if getattr(state, "second", False):
            second_checked.set()
        return result

    def validate_restore(objects):
        original_check(objects)
        if getattr(state, "second", False):
            second_checked.set()

    def run(first):
        state.second = not first
        conn = connections["default"]
        try:
            with tenant_schema_context(school.schema_name), transaction.atomic():
                if not first:
                    assert first_written.wait(15)
                restore = restore_first if first else not restore_first
                try:
                    if restore:
                        AssistedImportService(user=admin).restore_batch(batch.pk)
                    else:
                        GuardianService(user=admin).create_guardian(data)
                except (BusinessRuleViolationError, ValidationError):
                    return "denied"
                if first:
                    first_written.set()
                    assert release.wait(15)
                return "committed"
        finally:
            conn.close()

    with (
        patch.object(GuardianService, "_validate_cpf", validate_cpf),
        patch.object(AssistedImportSelector, "require_uncontested_identities", validate_restore),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        first = pool.submit(run, True)
        second = pool.submit(run, False)
        try:
            assert first_written.wait(15)
            assert second_checked.wait(15)
        finally:
            release.set()
        assert first.result(timeout=20) == "committed"
        assert second.result(timeout=20) == "denied"
    batch.refresh_from_db()
    assert batch.status == ("SEALED" if restore_first else "REVERTED")
    assert Guardian.objects.filter(cpf=data["cpf"]).count() == 1
    assert Student.objects.filter(origin_import_batch=batch).exists() is restore_first
