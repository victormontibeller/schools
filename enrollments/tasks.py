"""Tarefas Celery do modulo de matriculas."""

from __future__ import annotations

import logging

from celery import shared_task

from base.context import tenant_schema_context

logger = logging.getLogger(__name__)


@shared_task(name="enrollments.send_pending_documents_notification")
def send_pending_documents_notification(tenant_schema: str, student_id: str) -> None:
    """Notifica aluno/responsavel sobre pendencias documentais via canal configurado."""
    with tenant_schema_context(tenant_schema):
        from enrollments.selectors import EnrollmentApplicationSelector
        from notifications.channels import EmailChannel
        from students.selectors import StudentSelector

        selector = EnrollmentApplicationSelector()
        pending_docs = list(selector.get_student_pending_documents(student_id))

        if not pending_docs:
            logger.info(
                "Sem pendencias documentais para notificar",
                extra={"student_id": student_id},
            )
            return

        student = StudentSelector().get_student_by_id(student_id)
        recipient_email = student.email or (student.user.email if student.user else "")
        if not recipient_email:
            logger.warning(
                "Aluno sem email para notificacao de pendencias",
                extra={"student_id": student_id},
            )
            return

        doc_list = "\n".join(
            f"- {d.get_document_type_display()}: {d.description or 'Pendente'}"
            for d in pending_docs
        )

        channel = EmailChannel()
        channel.send(
            recipient_address=recipient_email,
            subject="Pendencias Documentais — School Manager",
            body=(
                f"Prezado(a) responsavel,\n\n"
                f"Identificamos pendencias documentais para o aluno "
                f"{student.get_full_name()} "
                f"(Matricula: {student.enrollment_number}):\n\n"
                f"{doc_list}\n\n"
                f"Por favor, regularize a documentacao na secretaria da escola.\n\n"
                f"Atenciosamente,\nSecretaria Escolar"
            ),
        )

        logger.info(
            "Notificacao de pendencias enviada",
            extra={"student_id": student_id, "doc_count": str(len(pending_docs))},
        )
