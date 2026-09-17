"""Manutenção idempotente e reconciliação fail-closed de imagens."""

import json
import os
import time
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management import call_command

from base.context import tenant_schema_context
from base.exceptions import BusinessRuleViolationError
from base.tests.images import png_upload
from core.media_selectors import ImageSelector
from core.media_services import ImageMaintenanceService
from core.models import CustomUser


@pytest.fixture(autouse=True)
def media(settings, tmp_path, monkeypatch):
    from base.tests.images import isolate_media_storages

    return isolate_media_storages(settings, monkeypatch, tmp_path)


@pytest.mark.django_db
def test_inventory_is_read_only_conversion_is_idempotent(
    user, media, django_capture_on_commit_callbacks
):
    from audit.models import AuditLog

    user.avatar.save("old.png", png_upload(), save=True)
    previous = user.avatar.name
    before = set(media.rglob("*.png"))
    audits_before = AuditLog.objects.count()
    output = StringIO()
    call_command("manage_images", "--schema", "public", stdout=output)
    assert json.loads(output.getvalue())["counts"] == {"eligible": 1}
    assert set(media.rglob("*.png")) == before
    assert AuditLog.objects.count() == audits_before
    with django_capture_on_commit_callbacks(execute=True):
        result = ImageMaintenanceService().run(["public"], operation="optimize", apply=True)
    assert result == {"converted": 1}
    user.refresh_from_db()
    assert user.avatar.name.startswith("public/avatars/users/optimized/v1/")
    assert not user.avatar.storage.exists(previous)
    assert AuditLog.objects.filter(object_id=str(user.pk)).count() == 1
    assert ImageMaintenanceService().run(["public"], operation="optimize", apply=True) == {
        "optimized": 1
    }


@pytest.mark.django_db
def test_conversion_preserves_shared_file_even_with_unknown_path(
    user, django_capture_on_commit_callbacks
):
    storage = storages["private"]
    old = storage.save("imported.png", png_upload())
    CustomUser.all_objects.filter(pk=user.pk).update(avatar=old)
    other = CustomUser.all_objects.create(email="inactive@test.test", avatar=old, is_active=False)
    with tenant_schema_context("public"):
        record = next(
            record for record in ImageSelector.records("public") if record.instance.pk == user.pk
        )
        with django_capture_on_commit_callbacks(execute=True):
            ImageMaintenanceService().optimize_record(record)
    assert storage.exists(old)
    other.refresh_from_db()
    assert other.avatar.name == old
    assert ImageSelector.is_referenced(storages["default"], old)


@pytest.mark.django_db
def test_conversion_rejects_stale_snapshot_and_keeps_missing_files(user):
    user.avatar.save("old.png", png_upload(), save=True)
    record = next(ImageSelector.records("public"))
    user.refresh_from_db()
    user.save()
    with tenant_schema_context("public"):
        with pytest.raises(BusinessRuleViolationError):
            ImageMaintenanceService().optimize_record(record)
    user.avatar.storage.delete(user.avatar.name)
    assert ImageMaintenanceService().run(["public"], operation="optimize", apply=True) == {
        "missing": 1
    }


@pytest.mark.django_db
def test_reconcile_removes_only_old_unreferenced_managed_files(user):
    storage = storages["private"]
    root = "public/avatars/users/"
    old = storage.save(root + uuid4().hex + ".png", png_upload())
    current = storage.save(root + uuid4().hex + ".png", png_upload())
    shared = storage.save(root + uuid4().hex + ".png", png_upload())
    unmanaged = storage.save(root + "notes.pdf", ContentFile(b"document"))
    document = storage.save("public/documents/enrollments/" + uuid4().hex + ".png", png_upload())
    for name in (old, shared, unmanaged, document):
        os.utime(storage.path(name), (time.time() - 90000,) * 2)
    CustomUser.all_objects.filter(pk=user.pk).update(avatar=shared, is_active=False)
    service = ImageMaintenanceService()
    assert service.run(["public"], operation="reconcile") == {"orphan": 1}
    assert storage.exists(old)
    assert service.run(["public"], operation="reconcile", apply=True) == {"removed": 1}
    assert not storage.exists(old)
    assert all(storage.exists(name) for name in (current, shared, unmanaged, document))


@pytest.mark.django_db
def test_reconcile_retains_file_if_reference_inventory_fails():
    storage = storages["private"]
    name = storage.save("public/avatars/users/" + uuid4().hex + ".png", png_upload())
    os.utime(storage.path(name), (time.time() - 90000,) * 2)
    with (
        tenant_schema_context("public"),
        patch.object(
            ImageSelector, "is_referenced", side_effect=RuntimeError("schema unavailable")
        ),
    ):
        with pytest.raises(RuntimeError):
            ImageMaintenanceService().reconcile_file(schema="public", alias="private", name=name)
    assert storage.exists(name)


@pytest.mark.django_db
def test_reconcile_retains_ambiguous_platform_legacy_namespace():
    from tenancy.models import School

    School.objects.create(schema_name="platform", name="Escola literal")
    storage = storages["private"]
    old = storage.save("platform/avatars/users/" + uuid4().hex + ".png", png_upload())
    os.utime(storage.path(old), (time.time() - 90000,) * 2)
    service = ImageMaintenanceService()
    assert not list(service.orphan_candidates("public"))
    assert not list(service.orphan_candidates("platform"))
    assert storage.exists(old)
