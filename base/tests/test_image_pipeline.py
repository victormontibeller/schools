"""Contratos de otimização e persistência de imagens gerenciadas."""

import logging
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.services import AccountService
from base.images import normalize_image


def upload(size=(1600, 800), mode="RGB", image_format="PNG", **kwargs):
    stream = BytesIO()
    Image.new(mode, size, (10, 100, 200, 80) if mode == "RGBA" else "white").save(
        stream, format=image_format, **kwargs
    )
    return SimpleUploadedFile("personal.png", stream.getvalue(), content_type="image/png")


def test_normalize_limits_size_and_preserves_alpha():
    result = normalize_image(upload(mode="RGBA"))
    with Image.open(result) as image:
        assert image.format == "WEBP"
        assert image.size == (512, 256)
        assert image.getpixel((0, 0))[3] == 80
        assert not image.info.get("exif")


def test_normalize_logo_is_lossless_and_does_not_upscale():
    result = normalize_image(upload(size=(32, 16), mode="RGBA"), logo=True)
    with Image.open(result) as image:
        assert image.size == (32, 16)
        assert image.getpixel((0, 0)) == (10, 100, 200, 80)


@pytest.mark.django_db
def test_update_user_persists_processed_file(user, isolated_media):
    with patch("base.ports.can_execute", return_value=True):
        result = AccountService(user=user).update_user(user.pk, {"avatar": upload()})
    assert "/optimized/v1/" in result.avatar.name
    with result.avatar.open() as saved:
        assert Image.open(saved).size == (512, 256)


@pytest.fixture()
def isolated_media(settings, tmp_path, monkeypatch):
    from base.tests.images import isolate_media_storages

    return isolate_media_storages(settings, monkeypatch, tmp_path)


def test_normalize_paletted_image_with_icc_and_transparency():
    from PIL import ImageCms

    stream = BytesIO()
    image = Image.new("P", (30, 20))
    image.putpalette([255, 0, 0] + [0, 0, 0] * 255)
    image.save(
        stream,
        format="PNG",
        transparency=0,
        icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes(),
    )
    result = normalize_image(SimpleUploadedFile("palette.png", stream.getvalue()), logo=True)
    with Image.open(result) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
        assert not image.info.get("icc_profile")


def test_normalize_applies_orientation_and_removes_metadata():
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "Personal metadata"
    result = normalize_image(upload(size=(600, 300), image_format="JPEG", exif=exif))
    with Image.open(result) as image:
        assert image.size == (256, 512)
        assert not image.getexif()


def test_normalize_does_not_log_personal_metadata_with_root_debug(caplog, monkeypatch):
    pillow_logger = logging.getLogger("PIL")
    monkeypatch.setattr(pillow_logger, "handlers", [*pillow_logger.handlers, caplog.handler])
    personal_marker = "SYNTHETIC_PRIVATE_EXIF_ARTIST"
    exif = Image.Exif()
    exif[315] = personal_marker
    image_upload = upload(size=(30, 20), image_format="JPEG", exif=exif)
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        logging.getLogger().debug("root_debug_remains_enabled")
        normalize_image(image_upload)
        pillow_logger.warning("synthetic_pillow_warning")
    assert "root_debug_remains_enabled" in caplog.text
    assert "synthetic_pillow_warning" in caplog.text
    assert personal_marker not in caplog.text


@pytest.mark.parametrize("kind", ["size", "pixels", "animation", "corrupt"])
def test_normalize_rejects_unsafe_content(kind):
    from django.core.exceptions import ValidationError

    if kind == "size":
        value = SimpleUploadedFile("image.png", b"x" * (5 * 1024 * 1024 + 1))
    elif kind == "pixels":
        value = upload(size=(5001, 5000))
    elif kind == "animation":
        value = upload(save_all=True, append_images=[Image.new("RGB", (1600, 800), "red")])
    else:
        value = SimpleUploadedFile("image.png", b"broken")
    with pytest.raises(ValidationError):
        normalize_image(value)


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["school", "unit", "user", "teacher", "guardian", "student"])
def test_create_and_update_optimize_each_domain(user, isolated_media, kind):
    from core.services import BusinessUnitService, SchoolService
    from guardians.services import GuardianService
    from guardians.tests.test_guardian_service import _guardian_data
    from students.services import StudentService
    from students.tests.test_student_service import _BASE_DATA
    from teachers.services import TeacherService

    field = "logo" if kind in {"school", "unit"} else "photo" if kind == "student" else "avatar"
    services = {
        "school": (SchoolService, "school"),
        "unit": (BusinessUnitService, "business_unit"),
        "user": (AccountService, "user"),
        "teacher": (TeacherService, "teacher"),
        "guardian": (GuardianService, "guardian"),
        "student": (StudentService, "student"),
    }
    cls, suffix = services[kind]
    data = {
        **_BASE_DATA,
        "hire_date": "2020-01-01",
        "name": "Unidade",
        "password": "Magnifico-1953-Rio!",
    }
    if kind == "guardian":
        data = _guardian_data(None)
    service = cls(user=user)
    instance = getattr(service, f"create_{suffix}")({**data, field: upload()})
    image_owner = instance.user if kind == "teacher" else instance
    original = getattr(image_owner, field)
    assert "/optimized/v1/" in original.name
    with original.open() as image_file:
        image = Image.open(image_file)
        assert image.format == "WEBP"
        assert max(image.size) == (1024 if field == "logo" else 512)
    previous = original.name
    instance = getattr(service, f"update_{suffix}")(
        instance.pk, {**data, field: upload(size=(200, 100))}
    )
    image_owner = instance.user if kind == "teacher" else instance
    current = getattr(image_owner, field)
    assert current.name != previous
    with current.open() as image_file:
        assert Image.open(image_file).size == (200, 100)
    unchanged = getattr(service, f"update_{suffix}")(instance.pk, {**data, field: None})
    assert getattr(unchanged.user if kind == "teacher" else unchanged, field).name == current.name


@pytest.mark.django_db
def test_rollback_removes_new_file_preserves_previous(user, isolated_media):
    service = AccountService(user=user)
    original = service.update_user(user.pk, {"avatar": upload()}).avatar.name
    before = set(isolated_media.rglob("*.webp"))
    with patch.object(service, "_record_audit", side_effect=RuntimeError("audit")):
        with pytest.raises(RuntimeError):
            service.update_user(user.pk, {"avatar": upload()})
    user.refresh_from_db()
    assert user.avatar.name == original
    assert set(isolated_media.rglob("*.webp")) == before


@pytest.mark.django_db
@pytest.mark.parametrize("child_fails", [True, False])
def test_nested_commands_compensate_only_rolled_back_files(user, isolated_media, child_fails):
    from base.services import BaseService, system_command

    class ParentService(BaseService):
        @system_command
        def run(self):
            target = AccountService(user=user)
            target.update_user(user.pk, {"avatar": upload()})
            if child_fails:
                with patch.object(target, "_record_audit", side_effect=RuntimeError("child")):
                    try:
                        target.update_user(user.pk, {"avatar": upload()})
                    except RuntimeError:
                        pass
            else:
                target.update_user(user.pk, {"avatar": upload()})
                raise RuntimeError("parent")

    if child_fails:
        ParentService().run()
        user.refresh_from_db()
        assert user.avatar.storage.exists(user.avatar.name)
        assert len(list(isolated_media.rglob("*.webp"))) == 1
    else:
        with pytest.raises(RuntimeError):
            ParentService().run()
        user.refresh_from_db()
        assert not user.avatar
        assert not list(isolated_media.rglob("*.webp"))


@pytest.mark.django_db(transaction=True)
def test_callback_failure_after_commit_never_deletes_saved_image(user, isolated_media):
    from django.db import transaction

    from base.services import BaseService, system_command

    class ParentService(BaseService):
        @system_command
        def run(self):
            transaction.on_commit(lambda: (_ for _ in ()).throw(RuntimeError("callback")))
            return AccountService(user=user).update_user(user.pk, {"avatar": upload()})

    with pytest.raises(RuntimeError, match="callback"):
        ParentService().run()
    user.refresh_from_db()
    assert user.avatar.storage.exists(user.avatar.name)


@pytest.mark.django_db
def test_long_schema_fits_storage_field_and_has_distinct_namespace(user, isolated_media):
    from base.context import tenant_schema_context
    from base.media import image_namespace
    from core.services import BusinessUnitService

    schema = "school_" + "x" * 56
    with tenant_schema_context(schema):
        unit = BusinessUnitService(user=user).create_business_unit(
            {"name": "Long", "logo": upload()}
        )
    assert len(unit.logo.name) <= 100
    assert image_namespace(schema).startswith("~s")
    assert image_namespace(schema) != image_namespace(schema[:-1] + "y")
    assert image_namespace("s_" + image_namespace(schema)[2:]) != image_namespace(schema)


@pytest.mark.django_db
def test_storage_cleanup_failure_does_not_fail_confirmed_update(
    user, isolated_media, django_capture_on_commit_callbacks
):
    service = AccountService(user=user)
    first = service.update_user(user.pk, {"avatar": upload()})
    storage = first.avatar.storage
    old = first.avatar.name
    with patch.object(storage, "delete", side_effect=OSError("unavailable")):
        with django_capture_on_commit_callbacks(execute=True):
            result = service.update_user(user.pk, {"avatar": upload()})
    assert result.avatar.name != old
    assert storage.exists(result.avatar.name)
    assert storage.exists(old)


@pytest.mark.django_db
def test_denied_command_never_writes_image(user, isolated_media):
    from base.exceptions import PermissionDeniedError

    with patch("base.ports.can_execute", return_value=False):
        with pytest.raises(PermissionDeniedError):
            AccountService(user=user).update_user(user.pk, {"avatar": upload()})
    assert not list(isolated_media.rglob("*.webp"))


@pytest.mark.django_db
def test_outer_transaction_rollback_is_recovered_by_reconciliation(user, isolated_media):
    import os
    import time

    from django.db import transaction

    from base.context import tenant_schema_context
    from core.media_services import ImageMaintenanceService

    with tenant_schema_context("public"):
        old = AccountService(user=user).update_user(user.pk, {"avatar": upload()}).avatar.name
        with pytest.raises(RuntimeError):
            with transaction.atomic():
                updated = AccountService(user=user).update_user(user.pk, {"avatar": upload()})
                orphan = updated.avatar.name
                raise RuntimeError("external rollback")
        user.refresh_from_db()
        assert user.avatar.name == old
        storage = user.avatar.storage
        assert storage.exists(orphan)
        os.utime(storage.path(orphan), (time.time() - 90000,) * 2)
        service = ImageMaintenanceService()
        assert service.run(["public"], operation="reconcile", apply=True) == {"removed": 1}
        assert storage.exists(old)
        assert not storage.exists(orphan)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kind",
    [
        "school",
        "unit",
        "user",
        "teacher",
        "teacher_edit",
        "guardian",
        "guardian_edit",
        "guardian_contact",
        "student",
        "student_edit",
    ],
)
def test_forms_use_same_bounded_image_validation(kind):
    from accounts.forms import UserEditForm
    from core.forms import BusinessUnitForm, SchoolEditForm
    from guardians.forms import GuardianContactEditForm, GuardianCreateForm, GuardianEditForm
    from students.forms import StudentEditForm, StudentForm
    from teachers.forms import TeacherEditForm, TeacherForm

    classes = {
        "school": SchoolEditForm,
        "unit": BusinessUnitForm,
        "user": UserEditForm,
        "teacher": TeacherForm,
        "teacher_edit": TeacherEditForm,
        "guardian": GuardianCreateForm,
        "guardian_edit": GuardianEditForm,
        "guardian_contact": GuardianContactEditForm,
        "student": StudentForm,
        "student_edit": StudentEditForm,
    }
    field = (
        "logo"
        if kind in {"school", "unit"}
        else "photo" if kind.startswith("student") else "avatar"
    )
    form = classes[kind](
        data={}, files={field: SimpleUploadedFile("bad.png", b"bad", content_type="image/png")}
    )
    assert not form.is_valid()
    assert "Arquivo de imagem inválido." in form.errors[field]


@pytest.mark.django_db
def test_stale_version_compensates_the_rejected_image(user, isolated_media):
    from base.exceptions import BusinessRuleViolationError

    service = AccountService(user=user)
    version = user.version
    updated = service.update_user(user.pk, {"avatar": upload(), "version": version})
    before = set(isolated_media.rglob("*.webp"))
    with pytest.raises(BusinessRuleViolationError):
        service.update_user(user.pk, {"avatar": upload(), "version": version})
    user.refresh_from_db()
    assert user.avatar.name == updated.avatar.name
    assert set(isolated_media.rglob("*.webp")) == before


@pytest.mark.django_db
def test_partial_storage_failure_is_compensated(user, isolated_media):
    from base.exceptions import ValidationError

    storage = user._meta.get_field("avatar").storage
    original_save = storage.save

    def fail_after_write(name, content, **kwargs):
        original_save(name, content, **kwargs)
        raise OSError("storage error")

    with patch.object(storage, "save", side_effect=fail_after_write):
        with pytest.raises(ValidationError):
            AccountService(user=user).update_user(user.pk, {"avatar": upload()})
    user.refresh_from_db()
    assert not user.avatar
    assert not list(isolated_media.rglob("*.webp"))
