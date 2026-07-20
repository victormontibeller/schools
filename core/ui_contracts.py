"""Contratos estáticos para shells canônicos e grades primárias."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from django.urls import NoReverseMatch, reverse

from core.ui_catalog import LIST_PAGE_CATALOG

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class GridContract:
    """Arquivos que, juntos, implementam uma grade operacional primária."""

    page_template: str
    scroll_template: str
    table_template: str


LIST_TEMPLATE_CONTRACTS: dict[str, tuple[str, str]] = {
    "academic_years_list": (
        "academic_calendar/templates/academic_calendar/academic_years_list.html",
        "academic_calendar/templates/academic_calendar/partials/academic_years_table.html",
    ),
    "announcement_list": (
        "notifications/templates/notifications/announcement_list.html",
        "notifications/templates/notifications/partials/announcements_table.html",
    ),
    "activities_list": (
        "activities/templates/activities/activities_list.html",
        "activities/templates/activities/partials/activities_table.html",
    ),
    "attendance_records_list": (
        "attendance/templates/attendance/records_list.html",
        "attendance/templates/attendance/partials/records_table.html",
    ),
    "billing_list": (
        "financeiro/templates/financeiro/billing_list.html",
        "financeiro/templates/financeiro/partials/billings_table.html",
    ),
    "business_unit_list": (
        "core/templates/core/business_units_list.html",
        "core/templates/core/partials/business_units_table.html",
    ),
    "classes_list": (
        "classes/templates/classes/classes_list.html",
        "classes/templates/classes/partials/classes_table.html",
    ),
    "diary_configuration": (
        "student_diary/templates/student_diary/configuration.html",
        "student_diary/templates/student_diary/partials/categories_table.html",
    ),
    "events_list": (
        "academic_calendar/templates/academic_calendar/events_list.html",
        "academic_calendar/templates/academic_calendar/partials/events_table.html",
    ),
    "guardians_list": (
        "guardians/templates/guardians/guardians_list.html",
        "guardians/templates/guardians/partials/guardians_table.html",
    ),
    "holidays_list": (
        "academic_calendar/templates/academic_calendar/holidays_list.html",
        "academic_calendar/templates/academic_calendar/partials/holidays_table.html",
    ),
    "justifications_list": (
        "attendance/templates/attendance/justifications_list.html",
        "attendance/templates/attendance/partials/justifications_table.html",
    ),
    "contract_list": (
        "financeiro/templates/financeiro/contract_list.html",
        "financeiro/templates/financeiro/partials/contracts_table.html",
    ),
    "financial_template_list": (
        "financeiro/templates/financeiro/template_list.html",
        "financeiro/templates/financeiro/partials/templates_table.html",
    ),
    "payment_queue": (
        "financeiro/templates/financeiro/payment_list.html",
        "financeiro/templates/financeiro/partials/payments_table.html",
    ),
    "reminder_history": (
        "financeiro/templates/financeiro/reminder_list.html",
        "financeiro/templates/financeiro/partials/reminders_table.html",
    ),
    "platform_school_list": (
        "tenancy/templates/tenancy/platform_school_list.html",
        "tenancy/templates/tenancy/partials/platform_schools_table.html",
    ),
    "platform_user_list": (
        "accounts/templates/accounts/platform_users_list.html",
        "accounts/templates/accounts/partials/platform_users_table.html",
    ),
    "rooms_list": (
        "rooms/templates/rooms/rooms_list.html",
        "rooms/templates/rooms/partials/rooms_table.html",
    ),
    "students_list": (
        "students/templates/students/students_list.html",
        "students/templates/students/partials/students_table.html",
    ),
    "subjects_list": (
        "teachers/templates/teachers/subjects_list.html",
        "teachers/templates/teachers/partials/subjects_table.html",
    ),
    "teachers_list": (
        "teachers/templates/teachers/teachers_list.html",
        "teachers/templates/teachers/partials/teachers_table.html",
    ),
    "time_slots_list": (
        "agenda/templates/agenda/time_slots_list.html",
        "agenda/templates/agenda/partials/time_slots_table.html",
    ),
    "users_list": (
        "accounts/templates/accounts/users_list.html",
        "accounts/templates/accounts/partials/users_table.html",
    ),
}

OPERATIONAL_GRID_CONTRACTS = (
    GridContract(
        "financeiro/templates/financeiro/contract_detail.html",
        "financeiro/templates/financeiro/contract_detail.html",
        "financeiro/templates/financeiro/contract_detail.html",
    ),
    GridContract(
        "financeiro/templates/financeiro/billing_detail.html",
        "financeiro/templates/financeiro/billing_detail.html",
        "financeiro/templates/financeiro/billing_detail.html",
    ),
    GridContract(
        "financeiro/templates/financeiro/overdue_report.html",
        "financeiro/templates/financeiro/overdue_report.html",
        "financeiro/templates/financeiro/overdue_report.html",
    ),
    GridContract(
        "financeiro/templates/financeiro/student_statement.html",
        "financeiro/templates/financeiro/student_statement.html",
        "financeiro/templates/financeiro/student_statement.html",
    ),
    GridContract(
        "financeiro/templates/financeiro/payment_batch_form.html",
        "financeiro/templates/financeiro/payment_batch_form.html",
        "financeiro/templates/financeiro/payment_batch_form.html",
    ),
    GridContract(
        "financeiro/templates/financeiro/payment_detail.html",
        "financeiro/templates/financeiro/payment_detail.html",
        "financeiro/templates/financeiro/payment_detail.html",
    ),
    GridContract(
        "student_diary/templates/student_diary/daily.html",
        "student_diary/templates/student_diary/partials/daily_roster_card.html",
        "student_diary/templates/student_diary/partials/daily_roster_card.html",
    ),
    GridContract(
        "core/templates/core/access/access_settings.html",
        "core/templates/core/access/partials/access_matrix_card.html",
        "core/templates/core/access/partials/access_matrix_card.html",
    ),
    GridContract(
        "academic_calendar/templates/academic_calendar/calendar_month.html",
        "academic_calendar/templates/academic_calendar/partials/calendar_workspace_content.html",
        "academic_calendar/templates/academic_calendar/partials/calendar_grid.html",
    ),
    GridContract(
        "agenda/templates/agenda/schedule_weekly.html",
        "agenda/templates/agenda/schedule_weekly.html",
        "agenda/templates/agenda/schedule_weekly.html",
    ),
    GridContract(
        "agenda/templates/agenda/teacher_schedule.html",
        "agenda/templates/agenda/teacher_schedule.html",
        "agenda/templates/agenda/teacher_schedule.html",
    ),
    GridContract(
        "attendance/templates/attendance/summary.html",
        "attendance/templates/attendance/summary.html",
        "attendance/templates/attendance/summary.html",
    ),
    GridContract(
        "attendance/templates/attendance/at_risk.html",
        "attendance/templates/attendance/at_risk.html",
        "attendance/templates/attendance/at_risk.html",
    ),
    GridContract(
        "attendance/templates/attendance/student_attendance.html",
        "attendance/templates/attendance/student_attendance.html",
        "attendance/templates/attendance/student_attendance.html",
    ),
    GridContract(
        "attendance/templates/attendance/record_fill.html",
        "attendance/templates/attendance/partials/attendance_fill_card.html",
        "attendance/templates/attendance/partials/attendance_fill_card.html",
    ),
)

MANUAL_SHELL_ALLOWLIST = {
    "accounts/change_password.html",
    "accounts/templates/accounts/user_detail.html",
    "activities/templates/activities/activity_detail.html",
    "addresses/templates/addresses/address_form.html",
    "classes/templates/classes/class_detail.html",
    "core/templates/core/business_unit_detail.html",
    "core/templates/core/school_detail.html",
    "design_system/design-system.html",
    "design_system/refs/duralux/index.html",
    "enrollments/templates/enrollments/application_detail.html",
    "enrollments/templates/enrollments/application_review.html",
    "enrollments/templates/enrollments/document_form.html",
    "enrollments/templates/enrollments/secretary_dashboard.html",
    "guardians/templates/guardians/guardian_detail.html",
    "guardians/templates/guardians/guardian_form.html",
    "notifications/templates/notifications/announcement_detail.html",
    "rooms/templates/rooms/room_detail.html",
    "student_diary/templates/student_diary/category_detail.html",
    "student_diary/templates/student_diary/publication_detail.html",
    "student_diary/templates/student_diary/student_history.html",
    "students/templates/students/student_profile.html",
    "teachers/templates/teachers/subject_detail.html",
    "teachers/templates/teachers/teacher_detail.html",
    "templates/auth/demo_signup_done.html",
    "templates/dashboard.html",
    "templates/form_base.html",
    "tenancy/templates/tenancy/platform_dashboard.html",
}

SECONDARY_TABLE_ALLOWLIST = {
    "activities/templates/activities/activity_detail.html",
    "classes/templates/classes/class_detail.html",
    "dashboard/templates/dashboard/executive.html",
    "dashboard/templates/dashboard/partials/operational_widgets.html",
    "design_system/design-system.html",
    "design_system/refs/duralux/index.html",
    "enrollments/templates/enrollments/application_detail.html",
    "enrollments/templates/enrollments/partials/applications_table.html",
    "student_diary/templates/student_diary/partials/category_options_card.html",
    "tenancy/templates/tenancy/platform_dashboard.html",
}

OBSOLETE_LAYOUT_CLASSES = {
    "sm-access-table-responsive",
    "sm-diary-main-content",
    "sm-diary-page-header",
    "sm-diary-table-responsive",
    "sm-list-card",
}


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _html_files() -> set[str]:
    ignored_parts = {".venv", "staticfiles", "node_modules"}
    return {
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in PROJECT_ROOT.rglob("*.html")
        if not ignored_parts.intersection(path.parts)
    }


def check_ui_contracts() -> list[str]:
    """Retorna violações determinísticas do contrato visual canônico."""
    errors: list[str] = []

    if set(LIST_TEMPLATE_CONTRACTS) != set(LIST_PAGE_CATALOG):
        errors.append("O catálogo e os templates de listagem possuem rotas diferentes.")

    for route_name, (page_template, table_template) in LIST_TEMPLATE_CONTRACTS.items():
        try:
            reverse(route_name)
        except NoReverseMatch:
            errors.append(f"Rota de listagem inválida: {route_name}")
        page_source = _read(page_template)
        table_source = _read(table_template)
        if '{% extends "list_page_base.html" %}' not in page_source:
            errors.append(f"Listagem fora do shell canônico: {page_template}")
        errors.extend(_check_scroll_contract(table_template, table_source))

    for definition in LIST_PAGE_CATALOG.values():
        for route_name in (definition.search_url, definition.create_url):
            if not route_name:
                continue
            try:
                reverse(route_name)
            except NoReverseMatch:
                errors.append(f"Rota inválida no catálogo de UI: {route_name}")

    for contract in OPERATIONAL_GRID_CONTRACTS:
        page_source = _read(contract.page_template)
        if '{% extends "page_shell_base.html" %}' not in page_source:
            errors.append(f"Grade fora do shell canônico: {contract.page_template}")
        errors.extend(
            _check_scroll_contract(contract.scroll_template, _read(contract.scroll_template))
        )
        table_source = _read(contract.table_template)
        for token in ("sm-sticky-table", "sm-sticky-table--first-column"):
            if token not in table_source:
                errors.append(f"{contract.table_template}: classe obrigatória ausente: {token}")

    html_files = _html_files()
    protected_pages = {page for page, _table in LIST_TEMPLATE_CONTRACTS.values()} | {
        contract.page_template for contract in OPERATIONAL_GRID_CONTRACTS
    }
    shell_sources = {"templates/page_shell_base.html", "templates/list_page_base.html"}
    for relative_path in html_files - MANUAL_SHELL_ALLOWLIST - protected_pages - shell_sources:
        source = _read(relative_path)
        if _has_class(source, "page-header") or _has_class(source, "main-content"):
            errors.append(f"Shell manual não registrado: {relative_path}")

    for relative_path in html_files:
        source = _read(relative_path)
        for class_name in OBSOLETE_LAYOUT_CLASSES:
            if _has_class(source, class_name):
                errors.append(f"Classe de layout obsoleta em {relative_path}: {class_name}")

    primary_tables = {table for _page, table in LIST_TEMPLATE_CONTRACTS.values()} | {
        contract.table_template for contract in OPERATIONAL_GRID_CONTRACTS
    }
    table_files = {path for path in html_files if "<table" in _read(path)}
    unregistered_tables = table_files - primary_tables - SECONDARY_TABLE_ALLOWLIST
    for relative_path in sorted(unregistered_tables):
        errors.append(f"Tabela sem contrato ou exceção registrada: {relative_path}")

    if (PROJECT_ROOT / "static" / "css" / "school-manager.css").exists():
        errors.append("CSS customizado duplicado em static/css/school-manager.css")
    if "school-manager.css' %}?v=" in _read("templates/base.html"):
        errors.append("Versionamento manual do CSS ainda está ativo em base.html")

    return sorted(set(errors))


def _check_scroll_contract(relative_path: str, source: str) -> list[str]:
    errors = []
    for token in ("table-responsive", "sm-scroll-region", 'tabindex="0"'):
        if token not in source:
            errors.append(f"{relative_path}: contrato de rolagem ausente: {token}")
    if "aria-label=" not in source and "aria-labelledby=" not in source:
        errors.append(f"{relative_path}: região rolável sem nome acessível")
    return errors


def _has_class(source: str, class_name: str) -> bool:
    """Encontra um token de classe exato sem confundir prefixos semelhantes."""
    return any(
        class_name in value.split() for value in re.findall(r'class=["\']([^"\']*)["\']', source)
    )
