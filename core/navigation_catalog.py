"""Composição da navegação lateral escolar por público, papel e rota ativa."""

from __future__ import annotations

STAFF_NAVIGATION = (
    {
        "label": "Acadêmico",
        "icon": "feather-book-open",
        "items": (
            {
                "label": "Turmas",
                "icon": "feather-layers",
                "url_name": "classes_list",
                "module": "classes",
                "prefixes": ("class_", "classes_"),
                "excluded_routes": ("class_attendance_summary",),
            },
            {
                "label": "Disciplinas",
                "icon": "feather-book",
                "url_name": "subjects_list",
                "module": "subjects",
                "prefixes": ("subject_", "subjects_"),
            },
            {
                "label": "Grade Horária",
                "icon": "feather-clock",
                "url_name": "time_slots_list",
                "module": "schedule",
                "prefixes": ("time_slot_", "time_slots_", "schedule_", "teacher_schedule"),
            },
            {
                "label": "Atividades",
                "icon": "feather-edit-3",
                "url_name": "activities_list",
                "module": "activities",
                "prefixes": ("activity_", "activities_"),
            },
            {
                "label": "Frequência",
                "icon": "feather-check-circle",
                "url_name": "attendance_records_list",
                "module": "attendance",
                "prefixes": (
                    "attendance_",
                    "class_attendance_",
                    "student_attendance",
                    "students_at_risk",
                    "justification_",
                    "justifications_",
                ),
            },
            {
                "label": "Agenda",
                "icon": "feather-heart",
                "url_name": "diary_daily",
                "module": "student_diary",
                "prefixes": ("diary_",),
            },
        ),
    },
    {
        "label": "Secretaria",
        "icon": "feather-file-text",
        "items": (
            {
                "label": "Professores",
                "icon": "feather-user-check",
                "url_name": "teachers_list",
                "module": "teachers",
                "prefixes": ("teacher_",),
                "excluded_routes": ("teacher_schedule",),
            },
            {
                "label": "Alunos",
                "icon": "feather-user",
                "url_name": "students_list",
                "module": "students",
                "prefixes": ("student_", "students_"),
                "excluded_routes": ("student_attendance", "student_attendance_class"),
            },
            {
                "label": "Responsáveis",
                "icon": "feather-users",
                "url_name": "guardians_list",
                "module": "guardians",
                "prefixes": ("guardian_", "guardians_"),
            },
            {
                "label": "Matrículas",
                "icon": "feather-clipboard",
                "url_name": "secretary_dashboard",
                "module": "enrollments",
                "routes": ("secretary_dashboard",),
                "prefixes": ("application_", "document_", "bulk_reenroll", "notify_"),
            },
        ),
    },
    {
        "label": "Coordenação",
        "icon": "feather-compass",
        "items": (
            {
                "label": "Calendário",
                "icon": "feather-calendar",
                "url_name": "calendar_month",
                "module": "academic_calendar",
                "prefixes": ("calendar_", "event_", "events_"),
            },
            {
                "label": "Feriados",
                "icon": "feather-flag",
                "url_name": "holidays_list",
                "module": "academic_calendar",
                "prefixes": ("holiday_", "holidays_"),
            },
            {
                "label": "Anos Letivos",
                "icon": "feather-calendar",
                "url_name": "academic_years_list",
                "module": "academic_calendar",
                "prefixes": ("academic_year_", "academic_years_"),
            },
            {
                "label": "Comunicados",
                "icon": "feather-message-square",
                "url_name": "announcement_list",
                "module": "notifications",
                "prefixes": ("announcement_",),
            },
        ),
    },
    {
        "label": "Financeiro",
        "icon": "feather-credit-card",
        "items": (
            {
                "label": "Visão Financeira",
                "icon": "feather-bar-chart-2",
                "url_name": "finance_dashboard",
                "module": "financeiro",
                "prefixes": ("finance_", "plan_", "billing_", "bulk_generate_"),
            },
        ),
    },
    {
        "label": "Administração",
        "icon": "feather-settings",
        "items": (
            {
                "label": "Salas",
                "icon": "feather-home",
                "url_name": "rooms_list",
                "module": "rooms",
                "prefixes": ("room_", "rooms_"),
            },
            {
                "label": "Unidades",
                "icon": "feather-briefcase",
                "url_name": "business_unit_list",
                "module": "core",
                "prefixes": ("business_unit_",),
            },
            {
                "label": "Escola",
                "icon": "feather-home",
                "url_name": "school_settings_detail",
                "module": "core",
                "prefixes": ("school_settings_",),
            },
            {
                "label": "Usuários",
                "icon": "feather-users",
                "url_name": "users_list",
                "module": "core",
                "prefixes": ("user_", "users_"),
            },
            {
                "label": "Acessos",
                "icon": "feather-shield",
                "url_name": "access_settings",
                "module": "__admin__",
                "prefixes": ("access_",),
            },
        ),
    },
)


TEACHER_NAVIGATION = (
    {
        "label": "Rotina Docente",
        "icon": "feather-edit-3",
        "items": (
            {
                "label": "Turmas",
                "icon": "feather-layers",
                "url_name": "classes_list",
                "module": "classes",
                "prefixes": ("class_", "classes_"),
                "excluded_routes": ("class_attendance_summary",),
            },
            {
                "label": "Grade Horária",
                "icon": "feather-clock",
                "url_name": "time_slots_list",
                "module": "schedule",
                "prefixes": ("time_slot_", "time_slots_", "schedule_", "teacher_schedule"),
            },
            {
                "label": "Atividades",
                "icon": "feather-edit-3",
                "url_name": "activities_list",
                "module": "activities",
                "prefixes": ("activity_", "activities_"),
            },
            {
                "label": "Frequência",
                "icon": "feather-check-circle",
                "url_name": "attendance_records_list",
                "module": "attendance",
                "prefixes": (
                    "attendance_",
                    "class_attendance_",
                    "student_attendance",
                    "students_at_risk",
                    "justification_",
                    "justifications_",
                ),
            },
            {
                "label": "Agenda",
                "icon": "feather-heart",
                "url_name": "diary_daily",
                "module": "student_diary",
                "prefixes": ("diary_",),
            },
        ),
    },
    {
        "label": "Planejamento",
        "icon": "feather-calendar",
        "items": (
            {
                "label": "Calendário",
                "icon": "feather-calendar",
                "url_name": "calendar_month",
                "module": "academic_calendar",
                "prefixes": ("calendar_", "event_", "events_", "holiday_", "holidays_"),
            },
            {
                "label": "Comunicados",
                "icon": "feather-message-square",
                "url_name": "announcement_list",
                "module": "notifications",
                "prefixes": ("announcement_",),
            },
        ),
    },
)


GUARDIAN_NAVIGATION = (
    {
        "label": "Acompanhamento",
        "icon": "feather-heart",
        "items": (
            {
                "label": "Aluno",
                "icon": "feather-user",
                "url_name": "dashboard",
                "ignore_url_name": True,
                "module": "students",
                "prefixes": ("student_",),
                "excluded_routes": ("student_attendance", "student_attendance_class"),
            },
            {
                "label": "Atividades",
                "icon": "feather-edit-3",
                "url_name": "activities_list",
                "module": "activities",
                "prefixes": ("activity_", "activities_"),
            },
            {
                "label": "Frequência",
                "icon": "feather-check-circle",
                "url_name": "dashboard",
                "ignore_url_name": True,
                "module": "attendance",
                "prefixes": ("student_attendance", "justification_", "justifications_"),
            },
            {
                "label": "Calendário",
                "icon": "feather-calendar",
                "url_name": "calendar_month",
                "module": "academic_calendar",
                "prefixes": ("calendar_",),
            },
            {
                "label": "Agenda",
                "icon": "feather-heart",
                "url_name": "dashboard",
                "ignore_url_name": True,
                "module": "student_diary",
                "prefixes": ("diary_student_",),
            },
        ),
    },
)
