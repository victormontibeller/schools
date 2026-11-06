"""Contratos estáticos para shells canônicos e grades primárias."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GridContract:
    """Arquivos que, juntos, implementam uma grade operacional primária."""

    page_template: str
    scroll_template: str
    table_template: str


LIST_TEMPLATE_CONTRACTS: dict[str, tuple[str, str]] = {
    "communication_delivery_list": (
        "notifications/templates/notifications/delivery_list.html",
        "notifications/templates/notifications/partials/deliveries_table.html",
    ),
    "service_request_list": (
        "service_requests/templates/service_requests/request_list.html",
        "service_requests/templates/service_requests/partials/requests_table.html",
    ),
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
    "enrollment_application_list": (
        "enrollments/templates/enrollments/application_list.html",
        "enrollments/templates/enrollments/partials/applications_table.html",
    ),
    "document_requirement_list": (
        "enrollments/templates/enrollments/document_requirement_list.html",
        "enrollments/templates/enrollments/partials/document_requirements_table.html",
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
    "schedule_classes_list": (
        "agenda/templates/agenda/schedule_classes_list.html",
        "agenda/templates/agenda/partials/schedule_classes_table.html",
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
        "financeiro/templates/financeiro/partials/overdue_details.html",
        "financeiro/templates/financeiro/partials/overdue_details.html",
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
        "agenda/templates/agenda/partials/schedule_matrix_workspace.html",
        "agenda/templates/agenda/partials/schedule_matrix_workspace.html",
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
    GridContract(
        "activities/templates/activities/activity_detail.html",
        "activities/templates/activities/partials/activity_score_card.html",
        "activities/templates/activities/partials/activity_score_card.html",
    ),
    GridContract(
        "enrollments/templates/enrollments/reenrollment_batch.html",
        "enrollments/templates/enrollments/partials/reenrollment_workspace.html",
        "enrollments/templates/enrollments/partials/reenrollment_workspace.html",
    ),
)

MANUAL_SHELL_ALLOWLIST = {
    "accounts/change_password.html",
    "accounts/templates/accounts/user_detail.html",
    "addresses/templates/addresses/address_form.html",
    "classes/templates/classes/class_detail.html",
    "core/templates/core/business_unit_detail.html",
    "core/templates/core/school_detail.html",
    "design_system/design-system.html",
    "design_system/refs/duralux/index.html",
    "enrollments/templates/enrollments/application_detail.html",
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
    "notifications/templates/notifications/announcement_detail.html",
    "classes/templates/classes/class_detail.html",
    "dashboard/templates/dashboard/executive.html",
    "dashboard/templates/dashboard/partials/operational_widgets.html",
    "design_system/design-system.html",
    "design_system/refs/duralux/index.html",
    "enrollments/templates/enrollments/partials/application_documents_card.html",
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

CANONICAL_TABS_TEMPLATE = "templates/partials/list_tabs.html"
DURALUX_REFERENCE_PREFIX = "design_system/refs/duralux/"
