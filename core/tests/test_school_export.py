"""Portabilidade privada com histórico, allowlist e falha atômica explícita."""

import datetime as dt
import json
import zipfile
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile

from audit.models import AuditLog
from base.context import current_tenant
from base.exceptions import BusinessRuleViolationError, PermissionDeniedError
from core.export_selectors import FIELDS
from core.export_services import SchoolExportService
from core.models import CustomUser, Role
from notifications.announcement_services import AnnouncementService
from notifications.models import MessageLog
from notifications.tests.test_announcement_workflow import family, publish
from students.models import Student
from tenancy.models import Domain, School

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture()
def school(user):
    school = School.objects.create(
        schema_name="test_school",
        name="Fictícia",
        settings={"email": {"secret": "SECRET-SETTING-SENTINEL"}, "diary_enabled": True},
    )
    Domain.objects.create(tenant=school, domain="school.example.test", is_primary=True)
    return school


def read_rows(archive, label):
    return [json.loads(line) for line in archive.read(f"data/{label}.jsonl").splitlines()]


def test_export_preserves_private_history_and_media_but_excludes_operational_secrets(
    user, school, tmp_path, django_capture_on_commit_callbacks, settings
):
    settings.MEDIA_ROOT = tmp_path / "source-media"
    tmp_path.chmod(0o700)
    account, guardian, _, links = family(user, children=2)
    draft, revision = publish(user)
    AnnouncementService(user=account).acknowledge_announcement(revision.pk)
    child = links[0].student
    child.photo.save("fixture.png", ContentFile(b"synthetic-private-file"))
    child.soft_delete(user=user)
    user.invitation_nonce = "00000000-0000-0000-0000-000000000099"
    user.save()
    secret_password = user.password
    MessageLog.objects.create(
        channel="EMAIL", recipient=user, payload={"invitation_token": "SECRET-TOKEN-SENTINEL"}
    )
    School.objects.create(schema_name="another", name="OTHER-SCHOOL-SENTINEL")
    target = tmp_path / "export.zip"
    with django_capture_on_commit_callbacks(execute=True):
        manifest = SchoolExportService(user=user).create_school_export(target)
    assert target.stat().st_mode & 0o777 == 0o600
    with zipfile.ZipFile(target) as archive:
        serialized = b"\n".join(archive.read(name) for name in archive.namelist())
        for secret in (
            secret_password,
            "SECRET-SETTING-SENTINEL",
            "SECRET-TOKEN-SENTINEL",
            "OTHER-SCHOOL-SENTINEL",
        ):
            assert secret.encode() not in serialized
        assert "notifications.MessageLog" not in manifest["counts"]
        exported = next(
            item for item in read_rows(archive, "students.Student") if item["id"] == str(child.pk)
        )
        assert exported["deleted_at"] and not exported["is_active"]
        assert archive.read(exported["media"]["photo"]) == b"synthetic-private-file"
        assert read_rows(archive, "notifications.AnnouncementRecipient")[0]["acknowledged_at"]
        assert len(read_rows(archive, "tenancy.School")) == 1
    assert AuditLog.objects.filter(
        model_name="School",
        object_id=str(school.pk),
        new_values__operation="school_export_requested",
    ).exists()


@pytest.mark.parametrize("role", ["SECRETARY", "COORDINATOR", "TEACHER", "FINANCE", "GUARDIAN"])
def test_export_denies_every_non_administrator(user, school, role, tmp_path):
    actor = CustomUser.objects.create_user(
        email=f"{role}@example.test", role=Role.objects.get(name=role)
    )
    with pytest.raises(PermissionDeniedError):
        SchoolExportService(user=actor).create_school_export(tmp_path / "denied.zip")
    assert not list(tmp_path.iterdir())


def test_export_denies_public_and_missing_media_and_rolls_back_audit(user, school, tmp_path):
    tmp_path.chmod(0o700)
    token = current_tenant.set("public")
    try:
        with pytest.raises(PermissionDeniedError):
            SchoolExportService(user=user).create_school_export(tmp_path / "public.zip")
    finally:
        current_tenant.reset(token)
    child = Student.objects.create(
        first_name="Fictícia",
        last_name="Criança",
        birth_date=dt.date(2022, 1, 1),
        enrollment_number="EXPORT",
        photo="test_school/missing/export.png",
    )
    with pytest.raises(BusinessRuleViolationError, match="mídia"):
        SchoolExportService(user=user).create_school_export(tmp_path / "missing.zip")
    assert not list(tmp_path.iterdir())
    child.photo = ""
    child.save()
    with (
        patch.object(SchoolExportService, "_record_audit", side_effect=RuntimeError),
        pytest.raises(RuntimeError),
    ):
        SchoolExportService(user=user).create_school_export(tmp_path / "audit.zip")
    assert not list(tmp_path.iterdir())


def test_export_finance_allowlist_includes_complete_business_history():
    expected = {
        "StudentFinancialContract",
        "BillingEntry",
        "FinancialPlanTemplate",
        "FinancialContractAmendment",
        "PaymentRecord",
        "PaymentAllocation",
        "FinancialSequence",
        "CollectionReminderPolicy",
    }
    assert {key.split(".")[1] for key in FIELDS if key.startswith("financeiro.")} == expected
    assert "idempotency_key" not in FIELDS["financeiro.PaymentRecord"]


def test_export_refuses_outer_transaction_without_leaving_private_staging(user, school, tmp_path):
    from django.db import transaction

    tmp_path.chmod(0o700)
    with transaction.atomic(), pytest.raises(BusinessRuleViolationError, match="outra transação"):
        SchoolExportService(user=user).create_school_export(tmp_path / "outer.zip")
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure", ["commit", "publish"])
def test_export_cleans_staging_on_commit_or_publication_failure(user, school, tmp_path, failure):
    from django.db import OperationalError, connection

    tmp_path.chmod(0o700)
    target = tmp_path / "output.zip"
    if failure == "commit":
        intercepted = patch.object(connection, "commit", side_effect=OperationalError("fixture"))
    else:
        intercepted = patch("core.export_archive.os.link", side_effect=FileExistsError)
    with (
        intercepted,
        patch("base.ports.media_is_referenced", side_effect=OperationalError("unavailable")),
        pytest.raises((OperationalError, FileExistsError)),
    ):
        SchoolExportService(user=user).create_school_export(target)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("unsafe", ["other_tenant", "symlink", "aliased_root_internal_symlink"])
def test_export_rejects_cross_tenant_or_symbolic_media(user, school, tmp_path, settings, unsafe):
    settings.MEDIA_ROOT = tmp_path / "source-media"
    source = settings.MEDIA_ROOT / "private"
    (source / "test_school").mkdir(parents=True)
    outside = tmp_path / "other-secret"
    outside.write_bytes(b"MUST-NOT-EXPORT")
    if unsafe == "aliased_root_internal_symlink":
        alias = tmp_path / "aliased-media"
        alias.symlink_to(settings.MEDIA_ROOT, target_is_directory=True)
        settings.MEDIA_ROOT = alias
        (source / "other_tenant").mkdir()
        (source / "other_tenant" / "secret.png").write_bytes(b"MUST-NOT-EXPORT")
        (source / "test_school" / "linked.png").symlink_to(source / "other_tenant" / "secret.png")
        name = "test_school/linked.png"
    elif unsafe == "symlink":
        (source / "test_school" / "linked.png").symlink_to(outside)
        name = "test_school/linked.png"
    else:
        name = "other_tenant/image.png"
    Student.objects.create(
        first_name="Criança",
        last_name="Fictícia",
        birth_date=dt.date(2022, 1, 1),
        enrollment_number="UNSAFE",
        photo=name,
    )
    output = tmp_path / "private-export"
    output.mkdir(mode=0o700)
    with pytest.raises(BusinessRuleViolationError):
        SchoolExportService(user=user).create_school_export(output / "denied.zip")
    assert not list(output.iterdir())
