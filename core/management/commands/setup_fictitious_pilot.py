"""Implantação de treinamento isolada, sem seed_dev e sem provedor real."""

import json
import os

from django.core.management.base import BaseCommand, CommandError

from accounts.selectors import AccountSelector
from base.context import tenant_schema_context
from base.exceptions import BusinessRuleViolationError, ValidationError
from core.fictitious import require_fictitious
from core.fictitious_journey_services import FictitiousJourneyService
from core.fictitious_services import FictitiousSetupService
from core.tenant_urls import school_url
from notifications.outbox_selectors import OutboxSelector
from notifications.outbox_services import OutboxService
from tenancy.services import PlatformSchoolService


class Command(BaseCommand):
    help = "Cria Escola Piloto Ipê e outra escola fictícia; exige modo local reservado."

    def handle(self, *args, **options):
        try:
            root = require_fictitious(schema="public")
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
            root.chmod(0o700)
            access = root / "access.json"
            if access.exists():
                state = json.loads(access.read_text())
                if state.get("completed"):
                    self.stdout.write(
                        "Ensaio já preparado. Consulte o arquivo privado access.json."
                    )
                    return
                raise CommandError(
                    "Implantação incompleta; preserve a evidência e corrija antes de repetir."
                )
            setup = FictitiousSetupService()
            with tenant_schema_context("public"):
                operator, password = setup.create_platform()
                state = {
                    "environment": "fictitious",
                    "completed": False,
                    "operator": {"email": operator.email, "password": password},
                    "schools": {},
                }
                self._store(access, state)
                platform = PlatformSchoolService(user=operator)
                for schema, name in (
                    ("piloto", "Escola Piloto Ipê"),
                    ("piloto_comparacao", "Escola Fictícia de Comparação"),
                ):
                    school = platform.create_platform_school(
                        {
                            "schema_name": schema,
                            "name": name,
                            "domain": f"{schema.replace('_', '-')}.localhost",
                        }
                    )
                    school = platform.update_platform_school(school.pk, {"diary_enabled": True})
                    admin_id = platform.create_school_administrator(
                        school.pk,
                        {
                            "first_name": "Administrador",
                            "last_name": "Fictício",
                            "email": "admin@example.test",
                        },
                    )
                    with tenant_schema_context(schema):
                        administrator, credential = setup.activate_account(
                            AccountSelector().get_by_id(admin_id), "staff"
                        )
                        school_state = {
                            "school_id": str(school.pk),
                            "url": school_url(school, "/"),
                            "credentials": {"ADMIN": credential},
                        }
                        state["schools"][schema] = school_state
                        self._store(access, state)
                        if schema == "piloto":
                            population = setup.create_population(administrator)
                            school_state["credentials"].update(population["credentials"])
                            school_state["evidence"] = (
                                FictitiousJourneyService().create_journey_evidence(population)
                            )
                        for delivery_id in list(OutboxSelector.pending_ids(limit=1000)):
                            OutboxService().dispatch(delivery_id)
                        self._store(access, state)
            state["completed"] = True
            self._store(access, state)
        except (BusinessRuleViolationError, ValidationError) as exc:
            raise CommandError(
                f"Ensaio interrompido ({type(exc).__name__}); nenhum provedor real foi utilizado."
            ) from None
        self.stdout.write(
            "Ensaio preparado. Consulte URLs e credenciais no arquivo privado access.json."
        )

    @staticmethod
    def _store(path, value):
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
