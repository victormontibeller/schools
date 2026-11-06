"""Capacidades independentes do atendimento, sem conceder módulos financeiros."""

DEPARTMENT_MODULES = {
    "SECRETARY": "requests_secretary",
    "COORDINATOR": "requests_coordination",
    "FINANCE": "requests_finance",
}


def build_request_modules(definition):
    staff = frozenset({"SECRETARY", "COORDINATOR", "FINANCE"})
    return (
        definition(
            "communication_delivery",
            "Falhas de comunicação",
            "Atendimento",
            staff,
            supported_actions=frozenset({"view", "edit"}),
        ),
        definition(
            "service_requests",
            "Solicitações privadas",
            "Atendimento",
            staff | {"GUARDIAN"},
            supported_actions=frozenset({"view", "create", "edit"}),
            scoped_roles=frozenset({"GUARDIAN"}),
        ),
        *(
            definition(
                key,
                f"Atender {label}",
                "Atendimento",
                staff,
                supported_actions=frozenset({"view", "edit"}),
            )
            for key, label in [
                ("requests_secretary", "Secretaria"),
                ("requests_coordination", "Coordenação"),
                ("requests_finance", "Financeiro"),
            ]
        ),
    )


REQUEST_DEFAULT_ACCESS = {
    "communication_delivery": {
        role: frozenset({"view", "edit"}) for role in ("SECRETARY", "COORDINATOR", "FINANCE")
    },
    "service_requests": {
        role: frozenset({"view", "create", "edit"} if role == "GUARDIAN" else {"view", "edit"})
        for role in ("SECRETARY", "COORDINATOR", "FINANCE", "GUARDIAN")
    },
    **{module: {role: frozenset({"view", "edit"})} for role, module in DEPARTMENT_MODULES.items()},
}
