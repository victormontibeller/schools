"""Constantes compartilhadas da composição da navegação."""

from core.access_catalog import DOCUMENT_REQUIREMENTS, REENROLLMENT

ATTENDANCE_NAVIGATION_PREFIXES = (
    "attendance_",
    "class_attendance_",
    "student_attendance",
    "students_at_risk",
    "justification_",
    "justifications_",
)

ENROLLMENT_WORKFLOW_NAVIGATION_ITEMS = (
    {
        "label": "Rematrícula em lote",
        "icon": "feather-refresh-cw",
        "url_name": "reenrollment_batch",
        "module": REENROLLMENT,
        "required_action": "view",
        "prefixes": ("reenrollment_",),
    },
    {
        "label": "Requisitos documentais",
        "icon": "feather-file-text",
        "url_name": "document_requirement_list",
        "module": DOCUMENT_REQUIREMENTS,
        "required_action": "view",
        "prefixes": ("document_requirement_",),
    },
)
