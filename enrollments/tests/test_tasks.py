"""Testes das notificações assíncronas de pendências documentais."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from enrollments.tasks import send_pending_documents_notification


def test_pending_documents_task_stops_when_there_are_no_documents():
    with patch(
        "enrollments.selectors.EnrollmentApplicationSelector.get_student_pending_documents",
        return_value=[],
    ):
        assert send_pending_documents_notification.run("public", "student-1") is None


def test_pending_documents_task_stops_when_student_has_no_recipient():
    document = SimpleNamespace()
    student = SimpleNamespace(email="", user=None)
    with (
        patch(
            "enrollments.selectors.EnrollmentApplicationSelector.get_student_pending_documents",
            return_value=[document],
        ),
        patch("students.selectors.StudentSelector.get_student_by_id", return_value=student),
        patch("notifications.channels.EmailChannel.send") as send,
    ):
        send_pending_documents_notification.run("public", "student-2")

    send.assert_not_called()


def test_pending_documents_task_sends_message_through_channel():
    document = SimpleNamespace(
        description="RG",
        get_document_type_display=Mock(return_value="Documento de identidade"),
    )
    student = SimpleNamespace(
        email="student@example.com",
        user=None,
        enrollment_number="ALU-2026-000001",
        get_full_name=Mock(return_value="Aluno Teste"),
    )
    with (
        patch(
            "enrollments.selectors.EnrollmentApplicationSelector.get_student_pending_documents",
            return_value=[document],
        ),
        patch("students.selectors.StudentSelector.get_student_by_id", return_value=student),
        patch("notifications.channels.EmailChannel.send") as send,
    ):
        send_pending_documents_notification.run("public", "student-3")

    send.assert_called_once()
    assert send.call_args.kwargs["recipient_address"] == student.email
