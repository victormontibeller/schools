"""Dados autorizados da escola corrente por allowlists estáticas revisáveis."""

from django.apps import apps

from base.context import active_tenant_schema
from base.exceptions import ObjectNotFoundError, PermissionDeniedError
from core import export_academic_catalog, export_identity_catalog, export_workflow_catalog
from core.models import CustomUser

CATALOGS = (export_identity_catalog, export_academic_catalog, export_workflow_catalog)
FIELDS = {key: value for catalog in CATALOGS for key, value in catalog.FIELDS.items()}
MEDIA_FIELDS = {key: value for catalog in CATALOGS for key, value in catalog.MEDIA_FIELDS.items()}
RELATION_FIELDS = {
    key: value for catalog in CATALOGS for key, value in catalog.RELATION_FIELDS.items()
}
COMMON_FIELDS = (
    "id",
    "created_at",
    "updated_at",
    "created_by_id",
    "updated_by_id",
    "is_active",
    "deleted_at",
    "deleted_by_id",
    "version",
)


class SchoolExportSelector:
    def authorized_school(self, user):
        from django.conf import settings
        from django.db import connection

        from tenancy.selectors import SchoolSelector

        schema = active_tenant_schema()
        if not settings.TESTING and connection.schema_name != schema:
            raise PermissionDeniedError("Contexto e conexão da escola não correspondem.")
        if schema == "public" or not user:
            raise PermissionDeniedError("Exportação exige administrador da própria escola.")
        actor = CustomUser.objects.select_related("role").filter(pk=user.pk, is_active=True).first()
        if not actor or not actor.role or actor.role.name != "ADMIN":
            raise PermissionDeniedError("Exportação exige administrador da própria escola.")
        try:
            school = SchoolSelector().get_active_by_schema(schema)
        except ObjectNotFoundError:
            raise PermissionDeniedError("Escola indisponível para exportação.") from None
        return school, actor

    def records(self, label, school):
        model = apps.get_model(label)
        manager = getattr(model, "all_objects", model._default_manager)
        query = manager.all().order_by("pk")
        if label == "tenancy.School":
            query = query.filter(pk=school.pk)
        elif label == "tenancy.Domain":
            query = query.filter(tenant_id=school.pk)
        elif label == "addresses.SchoolAddress":
            query = query.filter(school_id=school.pk)
        return query.iterator(chunk_size=250)

    def serialize(self, instance, label):
        # Metadata is also explicit; Domain only has its id.
        names = [name for name in COMMON_FIELDS if hasattr(instance, name)] + FIELDS[label]
        record = {name: getattr(instance, name) for name in names}
        for name in RELATION_FIELDS.get(label, ()):
            record[name] = list(getattr(instance, name).order_by("pk").values_list("pk", flat=True))
        if label == "tenancy.School":
            record["pilot_configuration"] = {
                "diary_enabled": bool(
                    (instance.settings or {})
                    .get("student_diary", {})
                    .get("interactive_enabled", False)
                ),
            }
        return record
