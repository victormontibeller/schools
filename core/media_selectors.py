"""Inventário somente-leitura de imagens em todos os schemas gerenciados."""

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from base.context import tenant_schema_context
from core.models import BusinessUnit, CustomUser
from guardians.contracts import Guardian
from students.contracts import Student
from tenancy.contracts import School


@dataclass(frozen=True)
class ImageRecord:
    """Referência versionada capturada no inventário de manutenção."""

    schema: str
    instance: object
    field: str
    name: str
    version: int


class ImageSelector:
    """Catálogo explícito exclui documentos e não duplica o avatar de Professor."""

    tenant_fields = (
        (BusinessUnit, "logo"),
        (CustomUser, "avatar"),
        (Guardian, "avatar"),
        (Student, "photo"),
    )

    @staticmethod
    def schemas() -> list[str]:
        """Inclui tenants inativos/excluídos e usuários da plataforma."""
        with tenant_schema_context("public"):
            return [
                "public",
                *School.all_objects.exclude(schema_name="public")
                .values_list("schema_name", flat=True)
                .distinct(),
            ]

    @classmethod
    def records(cls, schema: str):
        """Produz snapshots sem carregar arquivos no storage."""
        with tenant_schema_context(schema):
            pairs = ((CustomUser, "avatar"),) if schema == "public" else cls.tenant_fields
            if settings.TESTING:
                pairs = cls.tenant_fields
            for model, field in pairs:
                for obj in model.all_objects.exclude(**{field: ""}).iterator():
                    value = getattr(obj, field)
                    if value:
                        yield ImageRecord(schema, obj, field, value.name, obj.version)
            for obj in School.all_objects.filter(schema_name=schema).exclude(logo="").iterator():
                yield ImageRecord(schema, obj, "logo", obj.logo.name, obj.version)

    @staticmethod
    def storage_identity(storage):
        """Aliases locais com a mesma pasta representam o mesmo storage físico."""
        return Path(storage.location).resolve()

    @classmethod
    def is_referenced(cls, storage, name: str) -> bool:
        """Consulta todos os schemas; qualquer erro aborta a exclusão do arquivo."""
        identity = cls.storage_identity(storage)
        schemas = cls.schemas()
        for schema in schemas:
            with tenant_schema_context(schema):
                pairs = ((CustomUser, "avatar"),) if schema == "public" else cls.tenant_fields
                if settings.TESTING:
                    pairs = cls.tenant_fields
                for model, field in pairs:
                    if (
                        cls.storage_identity(model._meta.get_field(field).storage) == identity
                        and model.all_objects.filter(**{field: name}).exists()
                    ):
                        return True
        with tenant_schema_context("public"):
            return (
                cls.storage_identity(School._meta.get_field("logo").storage) == identity
                and School.all_objects.filter(logo=name).exists()
            )

    @staticmethod
    def current(record: ImageRecord):
        """Relê inclusive registros desativados, para compare-and-swap no service."""
        return type(record.instance).all_objects.get(pk=record.instance.pk)
