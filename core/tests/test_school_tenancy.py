"""Regressões PostgreSQL do catálogo público editado pelo tenant escolar."""

import os
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django_tenants.utils import schema_context
from PIL import Image

from audit.models import AuditLog
from base import context
from base.exceptions import PermissionDeniedError
from core.models import CustomUser
from core.selectors import SchoolSelector
from core.services import SchoolService
from core.tests.test_business_unit_views import _unit_payload
from tenancy.models import School

pytestmark = [
    pytest.mark.tenant,
    pytest.mark.skipif(
        os.environ.get("DJANGO_ENV") != "test_pg",
        reason="Requer PostgreSQL real e django-tenants.",
    ),
]


def _logo():
    stream = BytesIO()
    Image.new("RGB", (3, 3), "blue").save(stream, format="PNG")
    return SimpleUploadedFile("school.png", stream.getvalue(), "image/png")


class TestSchoolTenantUpdates(TenantTestCase):
    """A escola pública não pode referenciar a identidade privada do tenant."""

    @classmethod
    def get_test_schema_name(cls):
        return "school_logo_" + "a" * 51

    @classmethod
    def get_test_tenant_domain(cls):
        return "school-logo-a.test.local"

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Z Escola atual"
        return tenant

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        cls.other_school = School(schema_name="school_logo_b", name="A Outra escola")
        cls.other_school.save(verbosity=0)
        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.other_school.delete(force_drop=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        token = context.current_tenant.set(self.tenant.schema_name)
        self.addCleanup(context.current_tenant.reset, token)
        self.actor = CustomUser.objects.create_user(
            email="logo-admin@tenant.test", password="Senha123", is_superuser=True
        )
        self.service = SchoolService(user=self.actor)
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        self.enterContext(self.settings(MEDIA_ROOT=media.name))

    def _assert_tenant_audit(self, count):
        logs = AuditLog.objects.filter(model_name="School", object_id=str(self.tenant.pk))
        assert logs.count() == count
        assert set(logs.values_list("user_id", "tenant_schema", "operation")) == {
            (self.actor.pk, self.tenant.schema_name, "UPDATE")
        }
        with schema_context("public"):
            assert not CustomUser.objects.filter(pk=self.actor.pk).exists()
            assert not AuditLog.objects.filter(object_id=str(self.tenant.pk)).exists()
        with schema_context(self.other_school.schema_name):
            assert not AuditLog.objects.filter(object_id=str(self.tenant.pk)).exists()

    def test_update_school_accepts_actor_existing_only_in_tenant(self):
        updated = self.service.update_school(self.tenant.pk, {"trade_name": "Atualizada"})
        connection.check_constraints()
        updated.refresh_from_db()
        assert updated.trade_name == "Atualizada"
        assert updated.updated_by_id is None
        self._assert_tenant_audit(1)

    def test_update_school_with_logo_accepts_actor_existing_only_in_tenant(self):
        upload = _logo()
        updated = self.service.update_school(self.tenant.pk, {"logo": upload})
        connection.check_constraints()
        updated.refresh_from_db()
        assert updated.updated_by_id is None
        assert len(updated.logo.name) <= 100
        with updated.logo.open("rb") as stored:
            assert Image.open(stored).format == "WEBP"
        self._assert_tenant_audit(1)

    def test_get_current_school_uses_schema_instead_of_name_order(self):
        assert SchoolSelector().get_current_school().pk == self.tenant.pk
        with schema_context(self.other_school.schema_name):
            assert SchoolSelector().get_current_school().pk == self.other_school.pk
        with schema_context("school_without_catalog"):
            assert SchoolSelector().get_current_school() is None

    def test_update_rejects_other_school_before_storage_or_audit(self):
        original = School.objects.get(pk=self.other_school.pk)
        previous_audits = AuditLog.objects.count()
        for method, value in (
            (self.service.update_school, {"trade_name": "Forbidden"}),
            (self.service.update_school, {"logo": _logo()}),
        ):
            with patch.object(original.logo.storage, "save") as save:
                with pytest.raises(PermissionDeniedError):
                    method(self.other_school.pk, value)
                save.assert_not_called()
        original.refresh_from_db()
        assert original.trade_name == ""
        assert not original.logo
        assert AuditLog.objects.count() == previous_audits
        connection.check_constraints()

    def test_update_rolls_back_when_audit_fails(self):
        original = School.objects.get(pk=self.tenant.pk)
        previous_audits = AuditLog.objects.count()
        with patch.object(self.service, "_record_audit", side_effect=RuntimeError("audit")):
            with pytest.raises(RuntimeError, match="audit"):
                self.service.update_school(self.tenant.pk, {"trade_name": "Rollback"})
        original.refresh_from_db()
        assert original.trade_name == ""
        assert AuditLog.objects.count() == previous_audits
        connection.check_constraints()

    def test_update_school_with_logo_keeps_previous_file_when_audit_fails(self):
        original = self.service.update_school(self.tenant.pk, {"logo": _logo()})
        previous_name = original.logo.name
        with self.captureOnCommitCallbacks(execute=True):
            with patch.object(self.service, "_record_audit", side_effect=RuntimeError("audit")):
                with pytest.raises(RuntimeError, match="audit"):
                    self.service.update_school(self.tenant.pk, {"logo": _logo()})
        original.refresh_from_db()
        assert original.logo.name == previous_name
        assert original.logo.storage.exists(previous_name)
        self._assert_tenant_audit(1)
        connection.check_constraints()

    def test_update_preserves_public_actor_on_public_schema(self):
        with schema_context("public"):
            token = context.current_tenant.set("public")
            try:
                actor = CustomUser.objects.create_user(
                    email="logo-operator@public.test", password="Senha123", is_superuser=True
                )
                service = SchoolService(user=actor)
                service.update_school(self.tenant.pk, {"trade_name": "Operador"})
                updated = service.update_school(self.tenant.pk, {"logo": _logo()})
                connection.check_constraints()
                updated.refresh_from_db()
                assert updated.updated_by_id == actor.pk
                assert AuditLog.objects.filter(user=actor, model_name="School").count() == 2
            finally:
                context.current_tenant.reset(token)

    def _post_school(self, *, htmx):
        client = TenantClient(self.tenant)
        client.force_login(self.actor)
        headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
        response = client.post(
            "/app/escola/editar/",
            _unit_payload(name="Escola salva", logo=_logo()),
            **headers,
        )
        assert response.status_code == (200 if htmx else 302)
        connection.check_constraints()
        updated = School.objects.get(pk=self.tenant.pk)
        assert updated.name == "Escola salva"
        assert updated.logo and updated.logo.storage.exists(updated.logo.name)
        assert updated.updated_by_id is None
        if htmx:
            assert b"<html" not in response.content
            assert updated.logo.url.encode() in response.content
        else:
            assert response["Location"] == "/app/escola/"
        other = School.objects.get(pk=self.other_school.pk)
        assert other.name == "A Outra escola"
        assert not other.logo
        self._assert_tenant_audit(1)

    def test_post_school_persists_logo_and_fields(self):
        self._post_school(htmx=False)

    def test_post_school_persists_logo_and_fields_with_htmx(self):
        self._post_school(htmx=True)

    def test_private_avatar_is_optimized_and_isolated_in_postgresql(self):
        from accounts.services import AccountService
        from base.media import image_namespace

        with schema_context(self.other_school.schema_name):
            other = CustomUser.objects.create_user(
                id=self.actor.pk, email="other@tenant.test", password="Senha123", is_superuser=True
            )
        updated = AccountService(user=self.actor).update_user(self.actor.pk, {"avatar": _logo()})
        connection.check_constraints()
        assert updated.avatar.name.startswith(image_namespace(self.tenant.schema_name) + "/")
        assert len(updated.avatar.name) <= 100
        with updated.avatar.open() as content:
            assert Image.open(content).format == "WEBP"
        with pytest.raises(ValueError):
            _ = updated.avatar.url
        with schema_context(self.other_school.schema_name):
            other.refresh_from_db()
            assert not other.avatar
            assert not AuditLog.objects.filter(
                model_name="CustomUser", object_id=str(other.pk)
            ).exists()

    def test_maintenance_public_and_tenant_catalogs_do_not_duplicate_users(self):
        from base.context import tenant_schema_context
        from core.media_selectors import ImageSelector
        from core.media_services import ImageMaintenanceService

        self.actor.avatar = "legacy-missing.png"
        self.actor.save()
        with schema_context("public"):
            public_user = CustomUser.objects.create_user(
                email="public-image@test.test", password="Senha123", avatar="public-missing.png"
            )
        tenant_records = list(ImageSelector.records(self.tenant.schema_name))
        public_records = list(ImageSelector.records("public"))
        assert [(r.instance.pk, r.field) for r in tenant_records] == [(self.actor.pk, "avatar")]
        assert [(r.instance.pk, r.field) for r in public_records] == [(public_user.pk, "avatar")]
        assert list(ImageSelector.records(self.other_school.schema_name)) == []
        with tenant_schema_context(self.tenant.schema_name):
            results = ImageMaintenanceService().run(
                [self.tenant.schema_name], operation="optimize", apply=True
            )
        assert results == {"missing": 1}
        self.actor.refresh_from_db()
        assert self.actor.avatar.name == "legacy-missing.png"
