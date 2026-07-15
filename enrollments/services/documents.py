"""Regras de negócio dos documentos de matrícula."""

from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
from base.services import BaseService


class StudentDocumentService(BaseService):
    """Servico de regras de negocio para documentos escolares dos alunos."""

    def add_document(self, data: dict):
        """Adiciona um documento ao checklist do aluno."""
        from enrollments.models import StudentDocument
        from students.contracts import Student

        self.validate_required(data, ["student_id", "document_type"])

        student_id = data["student_id"]
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(student_id)) from None

        doc = StudentDocument.objects.create(
            student=student,
            application_id=data.get("application_id"),
            document_type=data["document_type"],
            description=data.get("description", ""),
            status=data.get("status", StudentDocument.Status.PENDING),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", doc)
        self._log(
            "Documento adicionado",
            document_id=str(doc.pk),
            student_id=str(student.pk),
            document_type=doc.document_type,
        )
        return doc

    def verify_document(self, document_id):
        """Marca o documento como verificado."""
        from enrollments.models import StudentDocument

        try:
            doc = StudentDocument.objects.select_related("student").get(pk=document_id)
        except StudentDocument.DoesNotExist:
            raise ObjectNotFoundError("StudentDocument", str(document_id)) from None

        if doc.status not in (StudentDocument.Status.SUBMITTED, StudentDocument.Status.PENDING):
            raise BusinessRuleViolationError("Documento ja foi verificado ou recusado.")

        old_status = doc.status
        doc.status = StudentDocument.Status.VERIFIED
        doc.verified_by = self.user
        doc.verified_at = timezone.now()
        doc.updated_by = self.user
        doc.save(update_fields=["status", "verified_by", "verified_at", "updated_by", "updated_at"])
        self._record_audit("UPDATE", doc, old_values={"status": old_status})
        self._log(
            "Documento verificado",
            document_id=str(doc.pk),
            student_id=str(doc.student.pk),
        )
        return doc

    def reject_document(self, document_id, reason: str = ""):
        """Recusa um documento com justificativa."""
        from enrollments.models import StudentDocument

        try:
            doc = StudentDocument.objects.select_related("student").get(pk=document_id)
        except StudentDocument.DoesNotExist:
            raise ObjectNotFoundError("StudentDocument", str(document_id)) from None

        if doc.status == StudentDocument.Status.REJECTED:
            raise BusinessRuleViolationError("Documento ja foi recusado.")

        old_status = doc.status
        doc.status = StudentDocument.Status.REJECTED
        doc.description = (reason or "").strip() or doc.description
        doc.updated_by = self.user
        doc.save(update_fields=["status", "description", "updated_by", "updated_at"])
        self._record_audit("UPDATE", doc, old_values={"status": old_status})
        self._log(
            "Documento recusado",
            document_id=str(doc.pk),
            student_id=str(doc.student.pk),
        )
        return doc

    def get_pending_documents(self, student_id):
        """Retorna documentos pendentes de um aluno."""
        from enrollments.models import StudentDocument

        return StudentDocument.objects.filter(
            student_id=student_id, status=StudentDocument.Status.PENDING
        )
