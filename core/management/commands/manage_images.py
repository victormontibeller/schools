"""Inventaria, otimiza ou reconcilia imagens em simulação por padrão."""

import json

from django.core.management.base import BaseCommand, CommandError

from core.media_selectors import ImageSelector
from core.media_services import ImageMaintenanceService


class Command(BaseCommand):
    """CLI operacional isolada por schema; --apply é sempre explícito."""

    help = "Inventaria/otimiza imagens e reconcilia órfãos; simulação por padrão."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--schema")
        group.add_argument("--all", action="store_true")
        parser.add_argument(
            "--operation", choices=("inventory", "optimize", "reconcile"), default="inventory"
        )
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        schemas = ImageSelector.schemas()
        if not options["all"]:
            if options["schema"] not in schemas:
                raise CommandError("Schema não encontrado no catálogo.")
            schemas = [options["schema"]]
        if options["apply"] and options["operation"] == "inventory":
            raise CommandError("Inventário não aceita --apply.")
        counts = ImageMaintenanceService().run(
            schemas, operation=options["operation"], apply=options["apply"]
        )
        self.stdout.write(
            json.dumps(
                {"mode": "apply" if options["apply"] else "dry-run", "counts": counts},
                sort_keys=True,
            )
        )
