"""Definições das capacidades granulares do contas a receber."""

FINANCE_OVERVIEW = "finance_overview"
FINANCE_TEMPLATES = "finance_templates"
FINANCE_CONTRACTS = "finance_contracts"
FINANCE_BILLINGS = "finance_billings"
FINANCE_PAYMENTS = "finance_payments"
FINANCE_REMINDERS = "finance_reminders"
FINANCE_REVENUE_REPORTS = "finance_revenue_reports"
FINANCE_OVERDUE_REPORTS = "finance_overdue_reports"


def build_finance_modules(
    module_definition,
    *,
    staff_roles,
    guardian: str,
    view: str,
    create: str,
    edit: str,
) -> tuple:
    """Compõe as oito linhas financeiras do catálogo central."""
    staff_and_guardian = staff_roles | {guardian}
    view_only = frozenset({view})
    standard_actions = frozenset({view, create, edit})
    return (
        module_definition(
            FINANCE_OVERVIEW,
            "Visão Financeira",
            "Financeiro",
            staff_and_guardian,
            supported_actions=view_only,
            scoped_roles=frozenset({guardian}),
        ),
        module_definition(
            FINANCE_TEMPLATES,
            "Modelos",
            "Financeiro",
            staff_roles,
            supported_actions=standard_actions,
        ),
        module_definition(
            FINANCE_CONTRACTS,
            "Contratos",
            "Financeiro",
            staff_roles,
            supported_actions=standard_actions,
        ),
        module_definition(
            FINANCE_BILLINGS,
            "Cobranças",
            "Financeiro",
            staff_and_guardian,
            supported_actions=standard_actions,
            scoped_roles=frozenset({guardian}),
            role_action_limits={guardian: view_only},
        ),
        module_definition(
            FINANCE_PAYMENTS,
            "Baixas e Conciliações",
            "Financeiro",
            staff_roles,
            supported_actions=standard_actions,
        ),
        module_definition(
            FINANCE_REMINDERS,
            "Lembretes",
            "Financeiro",
            staff_roles,
            supported_actions=frozenset({view, edit}),
        ),
        module_definition(
            FINANCE_REVENUE_REPORTS,
            "Competência e Caixa",
            "Financeiro",
            staff_roles,
            supported_actions=view_only,
        ),
        module_definition(
            FINANCE_OVERDUE_REPORTS,
            "Inadimplência",
            "Financeiro",
            staff_roles,
            supported_actions=view_only,
        ),
    )


def finance_default_access(*, finance: str, view: str, create: str, edit: str) -> dict:
    """Concede por padrão somente o teto operacional do papel Financeiro."""
    view_only = frozenset({view})
    standard_actions = frozenset({view, create, edit})
    return {
        FINANCE_OVERVIEW: {finance: view_only},
        FINANCE_TEMPLATES: {finance: standard_actions},
        FINANCE_CONTRACTS: {finance: standard_actions},
        FINANCE_BILLINGS: {finance: standard_actions},
        FINANCE_PAYMENTS: {finance: standard_actions},
        FINANCE_REMINDERS: {finance: frozenset({view, edit})},
        FINANCE_REVENUE_REPORTS: {finance: view_only},
        FINANCE_OVERDUE_REPORTS: {finance: view_only},
    }
