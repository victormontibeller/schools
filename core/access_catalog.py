"""Catálogo canônico de módulos, ações e padrões de acesso do tenant."""

from __future__ import annotations

from dataclasses import dataclass

ADMIN = "ADMIN"
SECRETARY = "SECRETARY"
COORDINATOR = "COORDINATOR"
TEACHER = "TEACHER"
FINANCE = "FINANCE"
GUARDIAN = "GUARDIAN"

CONFIGURABLE_ROLES = (SECRETARY, COORDINATOR, TEACHER, FINANCE, GUARDIAN)
ROLE_LABELS = {
    SECRETARY: "Secretaria",
    COORDINATOR: "Coordenação",
    TEACHER: "Professor",
    FINANCE: "Financeiro",
    GUARDIAN: "Responsável",
}
STAFF_ROLES = frozenset({SECRETARY, COORDINATOR, FINANCE})

VIEW = "view"
CREATE = "create"
EDIT = "edit"
DEACTIVATE = "deactivate"
ACTIONS = (VIEW, CREATE, EDIT, DEACTIVATE)
ACTION_LABELS = {
    VIEW: "Visualizar",
    CREATE: "Cadastrar",
    EDIT: "Editar",
    DEACTIVATE: "Desativar",
}
ACTION_SHORT_LABELS = {
    VIEW: "V",
    CREATE: "C",
    EDIT: "E",
    DEACTIVATE: "D",
}
ACTION_FIELDS = {
    VIEW: "can_view",
    CREATE: "can_create",
    EDIT: "can_edit",
    DEACTIVATE: "can_deactivate",
}


@dataclass(frozen=True, slots=True)
class ModuleDefinition:
    """Declara um módulo configurável e seus limites seguros."""

    key: str
    label: str
    department: str
    eligible_roles: frozenset[str]
    supported_actions: frozenset[str] = frozenset(ACTIONS)
    scoped_roles: frozenset[str] = frozenset()


_STAFF_AND_TEACHER = STAFF_ROLES | {TEACHER}
_PEDAGOGICAL = STAFF_ROLES | {TEACHER, GUARDIAN}

MODULES = (
    ModuleDefinition(
        "dashboard",
        "Visão geral",
        "Visão geral",
        frozenset(CONFIGURABLE_ROLES),
        frozenset({VIEW}),
    ),
    ModuleDefinition(
        "classes",
        "Turmas",
        "Acadêmico",
        _STAFF_AND_TEACHER,
        scoped_roles=frozenset({TEACHER}),
    ),
    ModuleDefinition(
        "subjects",
        "Disciplinas",
        "Acadêmico",
        _STAFF_AND_TEACHER,
        scoped_roles=frozenset({TEACHER}),
    ),
    ModuleDefinition(
        "schedule",
        "Grade horária",
        "Acadêmico",
        _STAFF_AND_TEACHER,
        scoped_roles=frozenset({TEACHER}),
    ),
    ModuleDefinition(
        "activities",
        "Atividades",
        "Acadêmico",
        _PEDAGOGICAL,
        scoped_roles=frozenset({TEACHER, GUARDIAN}),
    ),
    ModuleDefinition(
        "attendance",
        "Frequência",
        "Acadêmico",
        _PEDAGOGICAL,
        scoped_roles=frozenset({TEACHER, GUARDIAN}),
    ),
    ModuleDefinition(
        "student_diary",
        "Agenda",
        "Acadêmico",
        _PEDAGOGICAL,
        scoped_roles=frozenset({TEACHER, GUARDIAN}),
    ),
    ModuleDefinition("teachers", "Professores", "Secretaria", STAFF_ROLES),
    ModuleDefinition(
        "students",
        "Alunos",
        "Secretaria",
        frozenset(CONFIGURABLE_ROLES),
        scoped_roles=frozenset({TEACHER, GUARDIAN}),
    ),
    ModuleDefinition("guardians", "Responsáveis", "Secretaria", STAFF_ROLES),
    ModuleDefinition("enrollments", "Matrículas", "Secretaria", STAFF_ROLES),
    ModuleDefinition("rooms", "Salas", "Secretaria", STAFF_ROLES),
    ModuleDefinition(
        "diary_configuration",
        "Aspectos da rotina",
        "Secretaria",
        frozenset({SECRETARY, COORDINATOR}),
        supported_actions=frozenset({VIEW, CREATE, EDIT}),
    ),
    ModuleDefinition(
        "academic_calendar",
        "Calendário acadêmico",
        "Coordenação",
        _PEDAGOGICAL,
        scoped_roles=frozenset({GUARDIAN}),
    ),
    ModuleDefinition(
        "notifications",
        "Comunicados",
        "Coordenação",
        _PEDAGOGICAL,
        scoped_roles=frozenset({GUARDIAN}),
    ),
    ModuleDefinition("financeiro", "Financeiro", "Financeiro", STAFF_ROLES),
)

MODULES_BY_KEY = {module.key: module for module in MODULES}

# A ausência de uma ação significa negação. Desativar nunca é concedido por padrão.
DEFAULT_ACCESS: dict[str, dict[str, frozenset[str]]] = {
    "dashboard": {role: frozenset({VIEW}) for role in CONFIGURABLE_ROLES},
    "classes": {
        SECRETARY: frozenset({VIEW, CREATE, EDIT}),
        COORDINATOR: frozenset({VIEW, CREATE, EDIT}),
        TEACHER: frozenset({VIEW}),
        FINANCE: frozenset({VIEW}),
    },
    "subjects": {
        COORDINATOR: frozenset({VIEW, CREATE, EDIT}),
        TEACHER: frozenset({VIEW}),
    },
    "schedule": {
        COORDINATOR: frozenset({VIEW, CREATE, EDIT}),
        TEACHER: frozenset({VIEW}),
    },
    "activities": {
        COORDINATOR: frozenset({VIEW, CREATE, EDIT}),
        TEACHER: frozenset({VIEW, CREATE, EDIT}),
        GUARDIAN: frozenset({VIEW}),
    },
    "attendance": {
        COORDINATOR: frozenset({VIEW, CREATE, EDIT}),
        TEACHER: frozenset({VIEW, CREATE, EDIT}),
        GUARDIAN: frozenset({VIEW}),
    },
    "student_diary": {
        COORDINATOR: frozenset({VIEW, CREATE, EDIT}),
        TEACHER: frozenset({VIEW, CREATE, EDIT}),
        GUARDIAN: frozenset({VIEW}),
    },
    "teachers": {
        SECRETARY: frozenset({VIEW, CREATE, EDIT}),
        COORDINATOR: frozenset({VIEW}),
    },
    "students": {
        SECRETARY: frozenset({VIEW, CREATE, EDIT}),
        COORDINATOR: frozenset({VIEW}),
        TEACHER: frozenset({VIEW}),
        FINANCE: frozenset({VIEW}),
        GUARDIAN: frozenset({VIEW}),
    },
    "guardians": {
        SECRETARY: frozenset({VIEW, CREATE, EDIT}),
        COORDINATOR: frozenset({VIEW}),
    },
    "enrollments": {SECRETARY: frozenset({VIEW, CREATE, EDIT})},
    "rooms": {SECRETARY: frozenset({VIEW, CREATE, EDIT})},
    "diary_configuration": {
        SECRETARY: frozenset({VIEW, CREATE, EDIT}),
        COORDINATOR: frozenset({VIEW, CREATE, EDIT}),
    },
    "academic_calendar": {
        COORDINATOR: frozenset({VIEW, CREATE, EDIT}),
        TEACHER: frozenset({VIEW}),
        GUARDIAN: frozenset({VIEW}),
    },
    "notifications": {
        COORDINATOR: frozenset({VIEW, CREATE, EDIT}),
        TEACHER: frozenset({VIEW}),
        GUARDIAN: frozenset({VIEW}),
    },
    "financeiro": {FINANCE: frozenset({VIEW, CREATE, EDIT})},
}

APP_MODULES = {
    "academic_calendar": "academic_calendar",
    "activities": "activities",
    "agenda": "schedule",
    "attendance": "attendance",
    "classes": "classes",
    "dashboard": "dashboard",
    "enrollments": "enrollments",
    "financeiro": "financeiro",
    "guardians": "guardians",
    "notifications": "notifications",
    "rooms": "rooms",
    "student_diary": "student_diary",
    "students": "students",
    "teachers": "teachers",
}


def default_actions(module_key: str, role_name: str) -> frozenset[str]:
    """Retorna o conjunto inicial sem ampliar módulos ou papéis desconhecidos."""
    if module_key in DEFAULT_ACCESS:
        return DEFAULT_ACCESS[module_key].get(role_name, frozenset())
    module = MODULES_BY_KEY.get(module_key)
    if not module or role_name not in module.eligible_roles:
        return frozenset()
    if role_name in {TEACHER, GUARDIAN} and role_name not in module.scoped_roles:
        return frozenset()
    return department_defaults(module.department, role_name)


def module_for_app(app_label: str, *, subject: bool = False) -> str | None:
    """Resolve o módulo de produto de um app Django conhecido."""
    if app_label == "teachers" and subject:
        return "subjects"
    return APP_MODULES.get(app_label)


def action_for_operation(operation_name: str, *, is_post: bool = True) -> str:
    """Mapeia rotas e comandos para as quatro ações públicas."""
    normalized = operation_name.lower()
    operation_tokens = frozenset(normalized.replace("-", "_").split("_"))
    if operation_tokens & {"deactivate", "desativ", "unlink", "unenroll", "remove"}:
        return DEACTIVATE
    if operation_tokens & {"create", "novo", "nova", "add"}:
        return CREATE
    if is_post or operation_tokens.intersection(
        {
            "edit",
            "update",
            "approve",
            "reject",
            "cancel",
            "activate",
            "suspend",
            "generate",
            "record",
            "fill",
            "save",
            "apply",
            "reconcile",
            "review",
            "complete",
            "notify",
            "verify",
            "toggle",
            "link",
            "enroll",
            "transfer",
            "submit",
            "mark",
            "send",
            "register",
            "renegotiate",
            "restore",
        }
    ):
        return EDIT
    return VIEW


def department_defaults(department: str, role_name: str) -> frozenset[str]:
    """Define a herança segura aplicada a módulos futuros."""
    if department == "Acadêmico" and role_name in {COORDINATOR, TEACHER}:
        return frozenset({VIEW, CREATE, EDIT})
    if department == "Secretaria":
        if role_name == SECRETARY:
            return frozenset({VIEW, CREATE, EDIT})
        if role_name == COORDINATOR:
            return frozenset({VIEW})
    if department == "Coordenação":
        if role_name == COORDINATOR:
            return frozenset({VIEW, CREATE, EDIT})
        if role_name == TEACHER:
            return frozenset({VIEW})
    if department == "Financeiro" and role_name == FINANCE:
        return frozenset({VIEW, CREATE, EDIT})
    if department == "Acompanhamento" and role_name == GUARDIAN:
        return frozenset({VIEW})
    return frozenset()
