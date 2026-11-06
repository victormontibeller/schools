"""Exportação escolar explícita, auditada e sem credenciais no pacote."""

from django.db import connection, transaction

from base.exceptions import BusinessRuleViolationError
from base.services import BaseService
from core.export_archive import build_export_archive, publish_export
from core.export_selectors import SchoolExportSelector


class SchoolExportService(BaseService):
    def create_school_export(self, destination):
        """Publica o pacote somente depois de confirmar a auditoria na mesma transação."""
        if len(connection.atomic_blocks) > 1:
            raise BusinessRuleViolationError("Execute a exportação fora de outra transação.")
        school, actor = SchoolExportSelector().authorized_school(self.user)
        self.user = actor
        staging, manifest = build_export_archive(school, destination)
        from django.core.files.storage import FileSystemStorage

        from base.image_services import register_command_artifact

        register_command_artifact(FileSystemStorage(location=staging.parent), staging.name)
        try:
            self._record_audit(
                "UPDATE",
                school,
                new_values={"operation": "school_export_requested", "counts": manifest["counts"]},
            )
            self._log(
                "school_export_requested",
                school_id=str(school.pk),
                file_count=len(manifest["files"]),
            )
        except Exception:
            staging.unlink(missing_ok=True)
            raise
        transaction.on_commit(lambda: publish_export(staging, destination))
        return manifest
