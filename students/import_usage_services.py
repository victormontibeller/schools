"""Barreira transacional da carga: lotes ordenados antes das raízes e dependências."""

from base.context import active_tenant_schema
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
from base.services import BaseService, system_command
from students.models import AssistedImportBatch, Student


class ImportUsageService(BaseService):
    @system_command
    def seal_for_use(self, *, student_ids=(), guardian_ids=(), link_ids=(), allow_inactive=False):
        """Contrato interno: o comando autorizado chama antes de travar/criar dependências.

        Proveniência é imutável e consultada via all_objects, nunca pela instância do chamador.
        SEALED é terminal; objetos sem origem e lotes já selados não adquirem locks de lote.
        """
        from guardians.contracts import Guardian, StudentGuardian

        active_tenant_schema()
        identifiers = {
            Student: {str(pk) for pk in student_ids},
            Guardian: {str(pk) for pk in guardian_ids},
            StudentGuardian: {str(pk) for pk in link_ids},
        }
        links = list(StudentGuardian.all_objects.filter(pk__in=identifiers[StudentGuardian]))
        identifiers[Student].update(str(link.student_id) for link in links)
        identifiers[Guardian].update(str(link.guardian_id) for link in links)
        roots = []
        for model, ids in identifiers.items():
            items = list(model.all_objects.filter(pk__in=ids))
            if len(items) != len(ids):
                raise ObjectNotFoundError(model.__name__, "referência indisponível")
            roots.extend(items)
        batch_ids = {obj.origin_import_batch_id for obj in roots if obj.origin_import_batch_id}
        # Ordem global dos UUIDs elimina inversão quando um vínculo envolve mais de um lote.
        batches = AssistedImportBatch.all_objects.filter(pk__in=batch_ids).exclude(status="SEALED")
        for pk in batches.order_by("pk").values_list("pk", flat=True):
            batch = AssistedImportBatch.all_objects.select_for_update().get(pk=pk)
            if batch.status == "REVERTED":
                raise BusinessRuleViolationError("O cadastro pertence a uma carga desfeita.")
            if batch.status == "IMPORTED":
                old = {"status": batch.status}
                batch.status = AssistedImportBatch.Status.SEALED
                batch.updated_by = self.user
                batch.save()
                self._record_audit("UPDATE", batch, old_values=old)
                self._log("assisted_import_sealed", batch_id=str(batch.pk))
        # Undo pode ter vencido enquanto o comando esperava o lote. Nenhum objeto stale decide.
        if not allow_inactive:
            for model, ids in identifiers.items():
                if (
                    model.all_objects.filter(pk__in=ids)
                    .exclude(is_active=True, deleted_at=None)
                    .exists()
                ):
                    raise BusinessRuleViolationError(
                        "O cadastro não está ativo para esta operação."
                    )
