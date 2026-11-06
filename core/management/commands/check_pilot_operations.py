"""Monitora por processo externo ao Celery; entrega somente códigos e referência opaca."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from core.operational_monitor import monitor_snapshot, notify_monitor
from core.operations_selectors import OperationsSelector
from scripts.pilot_backup import BackupError


class Command(BaseCommand):
    help = "Verifica backup, HTTP, porta AMQP e atraso da outbox; alerta sem PII."

    def add_arguments(self, parser):
        for name in ("backup", "service-url", "alert-url", "state-file"):
            parser.add_argument(f"--{name}", required=True)

    def handle(self, *args, **options):
        try:
            health = OperationsSelector.communication_health()
        except DatabaseError:
            health = {
                "database_unavailable": True,
                "pending_deliveries": 0,
                "schools_with_overdue_outbox": 0,
            }
        try:
            snapshot = monitor_snapshot(
                backup=options["backup"],
                service_url=options["service_url"],
                broker_url=settings.CELERY_BROKER_URL,
                communication_health=health,
            )
            reference, emitted = notify_monitor(
                snapshot, alert_url=options["alert_url"], state_path=options["state_file"]
            )
        except (BackupError, OSError, ValueError):
            raise CommandError(
                "Monitor não concluiu; verifique a infraestrutura e o receptor."
            ) from None
        self.stdout.write(
            f"Referência {reference}; códigos={','.join(snapshot['codes']) or 'healthy'}; "
            f"alerta_novo={emitted}"
        )
