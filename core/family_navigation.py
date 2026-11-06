"""Composição do menu familiar com destinos autorizados."""

from core.navigation_constants import REQUEST_NAVIGATION

GUARDIAN_NAVIGATION = (
    REQUEST_NAVIGATION,
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
            {
                "label": "Comunicados",
                "icon": "feather-bell",
                "url_name": "announcement_list",
                "module": "notifications",
                "prefixes": ("announcement_",),
            },
            {
                "label": "Visão Financeira",
                "icon": "feather-credit-card",
                "url_name": "finance_dashboard",
                "module": "finance_overview",
            },
            {
                "label": "Cobranças",
                "icon": "feather-dollar-sign",
                "url_name": "billing_list",
                "module": "finance_billings",
                "prefixes": (
                    "billing_",
                    "student_financial_statement",
                    "payment_receipt_",
                ),
            },
        ),
    },
)
