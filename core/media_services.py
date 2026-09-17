"""Comandos internos de manutenção de imagens, invocados somente pela CLI."""

import hashlib
import re
from datetime import timedelta
from pathlib import Path

from django.core.files.storage import storages
from django.utils import timezone

from base.context import current_tenant, tenant_schema_context
from base.exceptions import BusinessRuleViolationError
from base.image_services import image_updates
from base.images import normalize_image
from base.media import image_namespace
from base.services import BaseService, system_command
from core.media_selectors import ImageRecord, ImageSelector

CATEGORIES = {
    "public": ("logos/schools", "logos/business-units"),
    "private": ("avatars/users", "avatars/guardians", "photos/students"),
}


class ImageMaintenanceService(BaseService):
    """Manutenção operacional explícita; não expõe comandos a rotas de produto."""

    @system_command
    def optimize_record(self, record: ImageRecord) -> str:
        """Converte uma referência em seu schema, com versão e nome esperados."""
        if current_tenant.get() != record.schema:
            raise BusinessRuleViolationError("O schema explícito não está ativo.")
        instance = ImageSelector.current(record)
        field = getattr(instance, record.field)
        if instance.version != record.version or field.name != record.name:
            raise BusinessRuleViolationError("A imagem foi alterada após o inventário.")
        if "/optimized/v1/" in field.name:
            return "optimized" if field.storage.exists(field.name) else "missing"
        old = self._snapshot(instance, [record.field])
        with field.storage.open(field.name, "rb") as source:
            updates = image_updates(instance, {record.field: source}, record.field)
        setattr(instance, record.field, updates[record.field])
        instance.updated_by = None
        instance.save(update_fields=[record.field, "updated_by", "updated_at"])
        self._record_audit("UPDATE", instance, old_values=old)
        self._log("image_optimized", entity_id=str(instance.pk))
        return "converted"

    def inspect_record(self, record: ImageRecord) -> str:
        """Valida sem escrever arquivos, registros ou auditoria."""
        field = getattr(record.instance, record.field)
        if "/optimized/v1/" in record.name:
            return "optimized" if field.storage.exists(record.name) else "missing"
        with field.storage.open(record.name, "rb") as source:
            normalize_image(source, logo=record.field == "logo")
        return "eligible"

    @system_command
    def reconcile_file(self, *, schema: str, alias: str, name: str) -> str:
        """Remove somente órfão gerenciado antigo após nova checagem global."""
        if current_tenant.get() != schema:
            raise BusinessRuleViolationError("O schema explícito não está ativo.")
        storage = storages[alias]
        if not self._eligible_file(schema, alias, name):
            return "retained"
        if ImageSelector.is_referenced(storage, name):
            return "referenced"
        # Arquivos órfãos não têm modelo para AuditLog; evento técnico é a trilha.
        storage.delete(name)
        self._log(
            "orphan_image_removed",
            schema_name=schema,
            storage_alias=alias,
            file_id=hashlib.sha256(name.encode()).hexdigest(),
        )
        return "removed"

    @staticmethod
    def _namespaces(schema: str) -> set[str]:
        namespaces = {image_namespace(schema), schema}
        # O prefixo antigo da plataforma é ambíguo se houver um tenant homônimo.
        if schema == "public" and "platform" not in ImageSelector.schemas():
            namespaces.add("platform")
        return namespaces

    @classmethod
    def _eligible_file(cls, schema: str, alias: str, name: str) -> bool:
        storage = storages[alias]
        namespaces = cls._namespaces(schema)
        roots = [
            f"{namespace}/{category}/" for namespace in namespaces for category in CATEGORIES[alias]
        ]
        if not any(name.startswith(root) for root in roots):
            return False
        suffix = next(name[len(root) :] for root in roots if name.startswith(root))
        if not re.fullmatch(
            r"(?:[a-f0-9]{32}\.(?:jpg|jpeg|png|webp)|optimized/v1/[a-f0-9]{32}\.webp)", suffix
        ):
            return False
        if schema == "platform" and not suffix.startswith("optimized/v1/"):
            return False
        path = Path(storage.path(name))
        if path.is_symlink() or not path.is_file():
            return False
        # Não atravessar symlinks em nenhuma parte do caminho.
        if path.resolve() != Path(storage.location).resolve() / name:
            return False
        return storage.get_modified_time(name) < timezone.now() - timedelta(hours=24)

    def orphan_candidates(self, schema: str):
        """Lista somente categorias de imagem, incluindo seus paths anteriores."""
        namespaces = self._namespaces(schema)
        for alias, categories in CATEGORIES.items():
            storage = storages[alias]
            for namespace in sorted(namespaces):
                for category in categories:
                    root = f"{namespace}/{category}"
                    yield from self._walk_candidates(schema, alias, storage, root)

    def _walk_candidates(self, schema, alias, storage, root):
        path = Path(storage.path(root))
        if (
            not path.exists()
            or path.is_symlink()
            or path.resolve() != Path(storage.location).resolve() / root
        ):
            return
        directories, files = storage.listdir(root)
        for filename in files:
            name = f"{root}/{filename}"
            if self._eligible_file(schema, alias, name) and not ImageSelector.is_referenced(
                storage, name
            ):
                yield alias, name
        for directory in directories:
            yield from self._walk_candidates(schema, alias, storage, f"{root}/{directory}")

    def run(self, schemas: list[str], *, operation: str, apply: bool = False) -> dict:
        """Isola cada registro; falhas individuais são contadas sem revelar PII."""
        counts = {}
        for schema in schemas:
            with tenant_schema_context(schema):
                items = (
                    self.orphan_candidates(schema)
                    if operation == "reconcile"
                    else ImageSelector.records(schema)
                )
                for item in items:
                    try:
                        if operation == "reconcile":
                            alias, name = item
                            result = (
                                self.reconcile_file(schema=schema, alias=alias, name=name)
                                if apply
                                else "orphan"
                            )
                        elif operation == "optimize" and apply:
                            result = self.optimize_record(item)
                        else:
                            result = self.inspect_record(item)
                    except FileNotFoundError:
                        result = "missing"
                        self._log(
                            "image_maintenance_missing",
                            level="warning",
                            schema_name=schema,
                            entity_id=(
                                str(item.instance.pk) if isinstance(item, ImageRecord) else None
                            ),
                            model_name=(
                                type(item.instance).__name__
                                if isinstance(item, ImageRecord)
                                else None
                            ),
                        )

                    except Exception as exc:
                        result = "failed"
                        self._log(
                            "image_maintenance_failed",
                            level="warning",
                            schema_name=schema,
                            error_type=type(exc).__name__,
                            entity_id=(
                                str(item.instance.pk) if isinstance(item, ImageRecord) else None
                            ),
                            model_name=(
                                type(item.instance).__name__
                                if isinstance(item, ImageRecord)
                                else None
                            ),
                        )
                    counts[result] = counts.get(result, 0) + 1
        return counts
