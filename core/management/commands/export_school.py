"""Portabilidade autenticada por identidade administrativa do próprio tenant."""

from django.core.management.base import BaseCommand, CommandError

from base.context import tenant_schema_context
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, PermissionDeniedError
from core.export_services import SchoolExportService
from core.models import CustomUser


class Command(BaseCommand):
    help = "Exporta a escola para pacote privado usando administrador escolar identificado."

    def add_arguments(self, parser):
        parser.add_argument("--schema", required=True)
        parser.add_argument("--actor-id", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        try:
            with tenant_schema_context(options["schema"]):
                actor = CustomUser.objects.get(pk=options["actor_id"])
                SchoolExportService(user=actor).create_school_export(options["output"])
        except (
            CustomUser.DoesNotExist,
            ValueError,
            BusinessRuleViolationError,
            ObjectNotFoundError,
            PermissionDeniedError,
        ):
            raise CommandError(
                "Exportação recusada. Confira escola, administrador e diretório privado."
            ) from None
        self.stdout.write(self.style.SUCCESS("Exportação escolar concluída no destino informado."))
