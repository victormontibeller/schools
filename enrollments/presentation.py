"""Composição de contexto e choices do fluxo HTTP de matrículas."""

from __future__ import annotations

from base.exceptions import ObjectNotFoundError
from base.parsers import parse_optional_uuid
from enrollments.selectors import ApplicationDetail, EnrollmentApplicationSelector


def application_detail_context(
    detail: ApplicationDetail, *, htmx_messages: bool = False
) -> dict[str, object]:
    """Converte a projeção materializada no contexto estável da ficha."""
    application = detail.application
    return {
        "application": application,
        "documents": detail.documents,
        "has_pending_required_documents": detail.has_pending_required_documents,
        "capacity": detail.capacity,
        "transitions": detail.transitions,
        "htmx_messages": htmx_messages,
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Matrículas", "url": "enrollment_application_list"},
            {"label": application.application_number, "url": None},
        ],
    }


def application_form_choices(student_id=None, *, student_search: str = "") -> dict:
    """Monta choices de aluno, turma e matrícula ativa sem ORM na view ou no form."""
    from students.selectors import StudentSelector

    selector = StudentSelector()
    students = list(selector.list_students(search=student_search, page_size=100).items)
    normalized_student_id = parse_optional_uuid(student_id)
    if normalized_student_id and all(item.pk != normalized_student_id for item in students):
        try:
            students.append(selector.get_student_by_id(normalized_student_id))
        except ObjectNotFoundError:
            pass
    enrollments = (
        EnrollmentApplicationSelector().active_enrollments(student_id=normalized_student_id)
        if normalized_student_id
        else ()
    )
    return {
        "student_choices": [(str(item.pk), str(item)) for item in students],
        "class_choices": class_choices(),
        "enrollment_choices": [(str(item.pk), str(item)) for item in enrollments],
    }


def class_choices(*, raw: bool = False):
    """Retorna turmas ordenadas como objetos ou choices de formulário."""
    from classes.selectors import ClassSelector

    classes = ClassSelector().list_ordered()
    return classes if raw else [(str(item.pk), str(item)) for item in classes]
