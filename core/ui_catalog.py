"""Catálogo tipado dos layouts canônicos de listagem."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ListPageDefinition:
    """Configuração estática exigida pelo shell canônico de listagem."""

    title: str
    search_url: str
    search_target: str
    create_url: str | None = None
    count_label: str = "registros"
    document_title: str | None = None

    def __post_init__(self) -> None:
        """Rejeita definições incompletas ainda durante a inicialização."""
        if not self.title.strip():
            raise ValueError("ListPageDefinition.title é obrigatório")
        if not self.search_url.strip():
            raise ValueError("ListPageDefinition.search_url é obrigatório")
        if not self.search_target.startswith("#") or len(self.search_target) == 1:
            raise ValueError("ListPageDefinition.search_target deve ser um seletor de id")

    @property
    def browser_title(self) -> str:
        """Retorna o título completo exibido pelo navegador."""
        return self.document_title or f"{self.title} — School Manager"


LIST_PAGE_CATALOG: dict[str, ListPageDefinition] = {
    "academic_years_list": ListPageDefinition(
        "Anos Letivos", "academic_years_list", "#academic-years-table", "academic_year_create"
    ),
    "announcement_list": ListPageDefinition(
        "Comunicados", "announcement_list", "#announcements-table"
    ),
    "activities_list": ListPageDefinition(
        "Atividades", "activities_list", "#activities-table", "activity_create"
    ),
    "attendance_records_list": ListPageDefinition(
        "Frequência",
        "attendance_records_list",
        "#attendance-records-table",
        "attendance_record_create",
    ),
    "billing_list": ListPageDefinition(
        "Cobranças", "billing_list", "#billings-table", "billing_create"
    ),
    "business_unit_list": ListPageDefinition(
        "Unidades", "business_unit_list", "#business-units-table", "business_unit_create"
    ),
    "classes_list": ListPageDefinition("Turmas", "classes_list", "#classes-table", "class_create"),
    "diary_configuration": ListPageDefinition(
        "Itens da Agenda",
        "diary_configuration",
        "#diary-categories-table",
        "diary_aspect_create",
        "itens",
    ),
    "events_list": ListPageDefinition("Eventos", "events_list", "#events-table", "event_create"),
    "guardians_list": ListPageDefinition(
        "Responsáveis", "guardians_list", "#guardians-table", "guardian_create"
    ),
    "holidays_list": ListPageDefinition(
        "Feriados", "holidays_list", "#holidays-table", "holiday_create"
    ),
    "justifications_list": ListPageDefinition(
        "Justificativas",
        "justifications_list",
        "#justifications-table",
        "justification_create",
    ),
    "contract_list": ListPageDefinition(
        "Contratos Financeiros", "contract_list", "#contracts-table", "contract_create"
    ),
    "financial_template_list": ListPageDefinition(
        "Modelos Financeiros",
        "financial_template_list",
        "#financial-templates-table",
        "financial_template_create",
    ),
    "payment_queue": ListPageDefinition(
        "Conciliações", "payment_queue", "#payments-table", "payment_create"
    ),
    "reminder_history": ListPageDefinition(
        "Histórico de Lembretes", "reminder_history", "#reminders-table"
    ),
    "platform_school_list": ListPageDefinition(
        "Escolas",
        "platform_school_list",
        "#platform-schools-table",
        "platform_school_create",
        document_title="Escolas — Administração da Plataforma",
    ),
    "platform_user_list": ListPageDefinition(
        "Operadores",
        "platform_user_list",
        "#platform-users-table",
        "platform_user_create",
        document_title="Operadores — Administração da Plataforma",
    ),
    "rooms_list": ListPageDefinition("Salas", "rooms_list", "#rooms-table", "room_create"),
    "students_list": ListPageDefinition(
        "Alunos e Responsáveis", "students_list", "#students-table", "student_create"
    ),
    "subjects_list": ListPageDefinition(
        "Disciplinas", "subjects_list", "#subjects-table", "subject_create"
    ),
    "teachers_list": ListPageDefinition(
        "Professores", "teachers_list", "#teachers-table", "teacher_create"
    ),
    "time_slots_list": ListPageDefinition(
        "Horários", "time_slots_list", "#time-slots-table", "time_slot_create"
    ),
    "users_list": ListPageDefinition("Usuários", "users_list", "#users-table"),
}


def get_list_page_definition(url_name: str | None) -> ListPageDefinition | None:
    """Resolve a definição canônica para a rota atual."""
    return LIST_PAGE_CATALOG.get(url_name or "")
