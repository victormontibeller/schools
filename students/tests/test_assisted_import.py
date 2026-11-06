"""Aceite da carga assistida e da reversão anterior ao uso operacional."""

from unittest.mock import patch

import pytest

from base.exceptions import BusinessRuleViolationError, PermissionDeniedError, ValidationError
from classes.models import Class, Enrollment
from core.models import CustomUser, Role
from guardians.models import Guardian, StudentGuardian
from students.import_services import AssistedImportService
from students.models import AssistedImportBatch, Student

pytestmark = pytest.mark.django_db


def files():
    return {
        "students": "source_id,first_name,last_name,birth_date,gender,cpf,"
        "rg_number,phone_mobile,email,blood_type\n"
        "S1,Criança,Fictícia,2022-01-01,NI,52998224725,123,11999999999,child@example.test,O+\n",
        "guardians": "source_id,first_name,last_name,birth_date,gender,cpf,"
        "rg_number,phone_mobile,email\n"
        "G1,Responsável,Fictício,1990-01-01,NI,11144477735,456,11999999999,parent@example.test\n",
        "links": "student_source_id,guardian_source_id,relationship_type,"
        "is_primary,has_custody,can_pickup\n"
        "S1,G1,LEGAL,1,1,1\n",
    }


def test_preview_imports_once_without_accounts_or_notifications(user):
    service = AssistedImportService(user=user)
    assert service.preview_import("pilot-1", files())["counts"] == {
        "students": 1,
        "guardians": 1,
        "links": 1,
    }
    assert not Student.objects.exists()
    with patch("base.events.publish_task_after_commit") as publish:
        batch = service.import_batch("pilot-1", files())
    assert service.import_batch("pilot-1", files()).pk == batch.pk
    assert (
        Student.objects.count() == Guardian.objects.count() == StudentGuardian.objects.count() == 1
    )
    assert CustomUser.objects.count() == 1
    assert Guardian.objects.get().user_id is None
    assert not Guardian.objects.get().accepts_email_notifications
    assert Student.objects.get().user_id is None
    publish.assert_not_called()
    assert len(batch.manifest) == 3


def test_import_rejects_all_rows_if_any_reference_is_invalid(user):
    data = files()
    data["links"] += "MISSING,G1,OUTRO,0,0,1\n"
    with pytest.raises(ValidationError):
        AssistedImportService(user=user).import_batch("bad", data)
    assert not Student.objects.exists()
    assert not AssistedImportBatch.objects.exists()


def test_import_rolls_back_all_rows_if_audit_fails(user):
    with patch(
        "students.import_services.AssistedImportService._record_audit", side_effect=RuntimeError
    ):
        with pytest.raises(RuntimeError):
            AssistedImportService(user=user).import_batch("fail", files())
    assert not Student.objects.exists()
    assert not Guardian.objects.exists()


def test_revert_soft_deletes_created_records_and_blocks_reimport(user):
    service = AssistedImportService(user=user)
    batch = service.import_batch("revert", files())
    service.deactivate_batch(batch.pk)
    assert not Student.objects.exists()
    assert Student.all_objects.count() == 1
    assert not Guardian.objects.exists()
    assert not StudentGuardian.objects.exists()
    with pytest.raises(BusinessRuleViolationError):
        service.import_batch("revert", files())
    with pytest.raises(ValidationError):
        service.import_batch("another-key", files())


def test_revert_rejects_dependency_or_changed_record(user):
    import datetime as dt

    service = AssistedImportService(user=user)
    batch = service.import_batch("used", files())
    child = Student.objects.get()
    cls = Class.objects.create(name="Infantil", academic_year=2026)
    Enrollment.objects.create(
        student=child, class_obj=cls, academic_year=2026, enrollment_date=dt.date(2026, 1, 1)
    )
    with pytest.raises(BusinessRuleViolationError):
        service.deactivate_batch(batch.pk)
    assert Student.objects.count() == 1
    assert StudentGuardian.objects.count() == 1


def test_import_denies_teacher_and_requires_explicit_custody(user):
    role = Role.objects.get(name=Role.Name.TEACHER)
    teacher = CustomUser.objects.create_user(email="teacher@example.test", role=role)
    with pytest.raises(PermissionDeniedError):
        AssistedImportService(user=teacher).preview_import("denied", files())
    data = files()
    data["links"] = data["links"].replace("LEGAL,1,1,1", "OUTRO,0,,1")
    with pytest.raises(ValidationError):
        AssistedImportService(user=user).import_batch("unknown-custody", data)


def test_revert_requires_guardian_permission_before_mutating(user):
    service = AssistedImportService(user=user)
    batch = service.import_batch("restricted-revert", files())
    from base.ports import can_execute as original_can_execute

    def permissions(actor, app, method, service_name=""):
        if app == "guardians" and method == "deactivate_guardian":
            return False
        return original_can_execute(actor, app, method, service_name)

    with patch("base.ports.can_execute", side_effect=permissions):
        with pytest.raises(PermissionDeniedError):
            service.deactivate_batch(batch.pk)
    assert Student.objects.count() == 1
    assert Guardian.objects.count() == 1
    assert StudentGuardian.objects.count() == 1
    batch.refresh_from_db()
    assert batch.status == AssistedImportBatch.Status.IMPORTED


def test_import_children_without_documents_contact_or_accounts_and_pickup_without_email(user):
    data = files()
    data["students"] = (
        "source_id,first_name,last_name,birth_date,gender,cpf,rg_number,phone_mobile,email,blood_type\n"
        "S1,Criança,Uma,2022-01-01,,,,,,\n"
        "S2,Criança,Duas,2023-01-01,,,,,,\n"
    )
    data["guardians"] = data["guardians"].replace("parent@example.test", "")
    data["links"] = data["links"].replace("LEGAL,1,1,1", "OUTRO,0,0,1")
    batch = AssistedImportService(user=user).import_batch("no-digital-child", data)
    assert batch.counts["students"] == 2
    assert Student.objects.filter(cpf__isnull=True, email="", user__isnull=True).count() == 2
    original_ids = set(Student.objects.values_list("pk", flat=True))
    service = AssistedImportService(user=user)
    service.deactivate_batch(batch.pk)
    restored = service.restore_batch(batch.pk)
    assert restored.status == "SEALED"
    assert set(Student.objects.values_list("pk", flat=True)) == original_ids
    assert not Student.objects.filter(user__isnull=False).exists()
    contact = Guardian.objects.get()
    link = StudentGuardian.objects.get()
    assert not contact.email and contact.user_id is None
    assert link.can_pickup and not link.has_custody
    from guardians.invitation_services import GuardianInvitationService

    with pytest.raises(ValidationError) as error:
        GuardianInvitationService(user=user).send_invitation(contact.pk)
    assert "email" in error.value.errors


def test_import_rejects_invalid_child_cpf_when_provided(user):
    data = files()
    data["students"] = data["students"].replace("52998224725", "123")
    with pytest.raises(ValidationError):
        AssistedImportService(user=user).import_batch("invalid-document", data)
    assert not Student.objects.exists()
