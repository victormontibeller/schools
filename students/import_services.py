"""Importação assistida atômica, idempotente e reversível antes do uso real."""

from base.context import active_tenant_schema
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import BaseService, service_command
from students.import_selectors import AssistedImportSelector
from students.import_validation import import_fingerprint, parse_import
from students.models import AssistedImportBatch


class AssistedImportService(BaseService):
    """Carga explícita de alunos, responsáveis e vínculos, sem criar acessos."""

    @service_command
    def preview_import(self, source_key, files):
        active_tenant_schema()
        self.validate_required({"source_key": source_key}, ["source_key"])
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.core.validators import validate_slug

        try:
            validate_slug(source_key)
        except DjangoValidationError:
            raise ValidationError(
                errors={"source_key": ["Use letras, números, hífen ou sublinhado."]}
            ) from None
        if len(source_key) > 100:
            raise ValidationError(errors={"source_key": ["Limite de 100 caracteres."]})
        digest = import_fingerprint(files)
        existing = AssistedImportBatch.objects.filter(source_key=source_key).first()
        if existing:
            if existing.status == AssistedImportBatch.Status.REVERTED:
                raise BusinessRuleViolationError(
                    "Lote desfeito não pode ser reaplicado; reconcilie os cadastros desativados."
                )
            if existing.fingerprint != digest:
                raise BusinessRuleViolationError(
                    "Identificador de lote já utilizado com arquivos diferentes."
                )
            return {
                "batch_id": str(existing.pk),
                "counts": existing.counts,
                "already_imported": True,
            }
        rows = parse_import(files)
        AssistedImportSelector.validate_existing(rows)
        return {
            "counts": {key: len(value) for key, value in rows.items()},
            "already_imported": False,
        }

    def import_batch(self, source_key, files):
        from guardians.services import GuardianService
        from students.services import StudentService

        active_tenant_schema()
        preview = self.preview_import(source_key, files)
        if preview["already_imported"]:
            return AssistedImportBatch.objects.get(pk=preview["batch_id"])
        batch, created = AssistedImportBatch.objects.get_or_create(
            source_key=source_key,
            defaults={
                "fingerprint": import_fingerprint(files),
                "counts": preview["counts"],
                "created_by": self.user,
                "updated_by": self.user,
            },
        )
        if not created:
            self.preview_import(source_key, files)
            return batch
        rows = parse_import(files)
        objects, manifest = {"students": {}, "guardians": {}}, []
        for kind, service, method in [
            ("students", StudentService(user=self.user), "create_student"),
            ("guardians", GuardianService(user=self.user), "create_guardian"),
        ]:
            for row in rows[kind]:
                obj = getattr(service, method)(row, _import_batch=batch)
                objects[kind][row["source_id"]] = obj
                manifest.append(self._manifest_entry(obj, row["source_id"]))
        for row in rows["links"]:
            obj = GuardianService(user=self.user).link_student(
                objects["guardians"][row["guardian_source_id"]].pk,
                objects["students"][row["student_source_id"]].pk,
                row,
                _import_batch=batch,
            )
            manifest.append(
                self._manifest_entry(obj, f"{row['student_source_id']}:{row['guardian_source_id']}")
            )
        batch.manifest = manifest
        batch.save()
        self._record_audit("INSERT", batch)
        self._log("assisted_import_completed", batch_id=str(batch.pk), total=len(manifest))
        return batch

    def deactivate_batch(self, batch_id):
        from guardians.contracts import Guardian, StudentGuardian
        from students.models import Student

        active_tenant_schema()
        from base.exceptions import PermissionDeniedError
        from base.ports import can_execute

        if not can_execute(self.user, "guardians", "deactivate_guardian", "GuardianService"):
            raise PermissionDeniedError(
                "A reversão também exige permissão para desativar responsáveis."
            )
        try:
            batch = AssistedImportBatch.objects.select_for_update().get(pk=batch_id)
        except AssistedImportBatch.DoesNotExist:
            raise ObjectNotFoundError("AssistedImportBatch", str(batch_id)) from None
        if batch.status != AssistedImportBatch.Status.IMPORTED:
            raise BusinessRuleViolationError("Lote em uso ou desfeito não admite reversão.")
        models = {model._meta.label: model for model in (Student, Guardian, StudentGuardian)}
        objects = []
        for item in batch.manifest:
            obj = models[item["model"]].all_objects.select_for_update().get(pk=item["object_id"])
            if obj.version != item["version"] or obj.deleted_at:
                raise BusinessRuleViolationError(
                    "Cadastros do lote foram alterados; aplique correção auditada."
                )
            objects.append(obj)
        AssistedImportSelector.require_unused(objects, batch.manifest)
        for obj in reversed(objects):
            self._deactivate(type(obj), obj.pk, type(obj).__name__)
        for item in batch.manifest:
            item["reverted_version"] = (
                models[item["model"]].all_objects.get(pk=item["object_id"]).version
            )
        old = self._snapshot(batch, ["status"])
        batch.status = AssistedImportBatch.Status.REVERTED
        batch.updated_by = self.user
        batch.save()
        self._record_audit("UPDATE", batch, old_values=old)
        self._log("assisted_import_reverted", batch_id=str(batch.pk), total=len(objects))
        return batch

    def restore_batch(self, batch_id):
        """Recuperação explícita integral; sela o lote e permite correções normais."""
        from base.exceptions import PermissionDeniedError
        from base.ports import can_execute
        from guardians.contracts import Guardian, StudentGuardian, guardian_identity_write
        from students.models import Student

        active_tenant_schema()
        if not can_execute(self.user, "guardians", "update_guardian", "GuardianService"):
            raise PermissionDeniedError("A recuperação exige edição de responsáveis.")
        try:
            batch = AssistedImportBatch.objects.select_for_update().get(pk=batch_id)
        except AssistedImportBatch.DoesNotExist:
            raise ObjectNotFoundError("AssistedImportBatch", str(batch_id)) from None
        if batch.status != "REVERTED":
            raise BusinessRuleViolationError("Somente um lote desfeito pode ser recuperado.")
        models = {model._meta.label: model for model in (Student, Guardian, StudentGuardian)}
        objects = []
        for item in batch.manifest:
            obj = models[item["model"]].all_objects.select_for_update().get(pk=item["object_id"])
            if (
                obj.version != item.get("reverted_version")
                or not obj.deleted_at
                or obj.is_active
                or obj.origin_import_batch_id != batch.pk
            ):
                raise BusinessRuleViolationError(
                    "O manifesto mudou; a recuperação foi interrompida."
                )
            objects.append(obj)
        AssistedImportSelector.require_unused(objects, batch.manifest)
        AssistedImportSelector.require_uncontested_identities(objects)
        for obj in objects:
            old = self._snapshot(obj, ["is_active", "deleted_at"])
            with guardian_identity_write():
                obj.restore(user=self.user)
            self._record_audit("UPDATE", obj, old_values=old)
        batch.status = AssistedImportBatch.Status.SEALED
        batch.updated_by = self.user
        batch.save()
        self._record_audit("UPDATE", batch, old_values={"status": "REVERTED"})
        self._log("assisted_import_restored_for_correction", batch_id=str(batch.pk))
        return batch

    @staticmethod
    def _manifest_entry(obj, source_id):
        return {
            "source_id": source_id,
            "model": obj._meta.label,
            "object_id": str(obj.pk),
            "version": obj.version,
            "created": True,
        }
