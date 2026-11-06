"""Prévia e aplicação explícita de uma carga assistida de implantação."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from base.context import tenant_schema_context
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)


class Command(BaseCommand):
    help = "Valida/importa CSVs sem criar contas ou enviar convites; prévia é o padrão."

    def add_arguments(self, parser):
        parser.add_argument("--schema", required=True)
        parser.add_argument(
            "--actor", required=True, help="UUID do administrador/secretaria no tenant."
        )
        parser.add_argument("--source-key")
        parser.add_argument("--students")
        parser.add_argument("--guardians")
        parser.add_argument("--links")
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--apply", action="store_true")
        group.add_argument("--revert", help="UUID do lote a desfazer antes do uso operacional.")
        group.add_argument(
            "--restore", help="Recupera integralmente um lote desfeito para correção."
        )

    def handle(self, *args, **options):
        from accounts.selectors import AccountSelector
        from students.import_services import AssistedImportService
        from tenancy.selectors import SchoolSelector

        try:
            SchoolSelector().get_active_by_schema(options["schema"])
            with tenant_schema_context(options["schema"]):
                actor = AccountSelector().get_by_id(options["actor"])
                service = AssistedImportService(user=actor)
                if options["revert"] or options["restore"]:
                    batch = (
                        service.deactivate_batch(options["revert"])
                        if options["revert"]
                        else service.restore_batch(options["restore"])
                    )
                    result = {
                        "batch_id": str(batch.pk),
                        "status": batch.status,
                        "counts": batch.counts,
                    }
                else:
                    if not options["source_key"] or not all(
                        options[key] for key in ("students", "guardians", "links")
                    ):
                        raise CommandError("Informe source-key e os três arquivos CSV.")
                    files = {
                        key: Path(options[key]).read_text(encoding="utf-8-sig")
                        for key in ("students", "guardians", "links")
                    }
                    if options["apply"]:
                        batch = service.import_batch(options["source_key"], files)
                        result = {
                            "batch_id": str(batch.pk),
                            "status": batch.status,
                            "counts": batch.counts,
                        }
                    else:
                        result = service.preview_import(options["source_key"], files)
                self.stdout.write(json.dumps(result, ensure_ascii=False))
        except ValidationError as exc:
            raise CommandError(json.dumps(exc.errors, ensure_ascii=False)) from None
        except (BusinessRuleViolationError, ObjectNotFoundError, PermissionDeniedError) as exc:
            raise CommandError(str(exc)) from None
        except (OSError, UnicodeError):
            raise CommandError("Não foi possível ler os arquivos CSV em UTF-8.") from None
