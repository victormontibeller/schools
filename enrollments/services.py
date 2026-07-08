"""EnrollmentService: regras de negocio para matriculas, rematriculas e transferencias."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
from base.services import BaseService

if TYPE_CHECKING:
    from enrollments.models import EnrollmentApplication

logger = logging.getLogger(__name__)


def _generate_application_number() -> str:
    """Gera protocolo unico de matricula baseado em timestamp."""
    from datetime import datetime

    now = datetime.now()
    return f"MAT-{now.strftime('%Y%m%d%H%M%S%f')}"


class EnrollmentApplicationService(BaseService):
    """Servico de regras de negocio para solicitacoes de matricula."""

    ACTIVE_STATUSES = (
        "PRE_ENROLLMENT",
        "UNDER_REVIEW",
        "APPROVED",
        "ENROLLED",
    )
    PENDING_STATUSES = (
        "PRE_ENROLLMENT",
        "UNDER_REVIEW",
        "APPROVED",
    )

    def create_application(self, data: dict) -> EnrollmentApplication:
        """Cria uma pre-matricula ou solicitacao de matricula."""
        from classes.models import Class
        from enrollments.models import EnrollmentApplication
        from students.models import Student

        self.validate_required(data, ["student_id", "class_obj_id", "academic_year"])

        application_type = data.get("application_type", EnrollmentApplication.ApplicationType.NEW)

        if application_type in (
            EnrollmentApplication.ApplicationType.TRANSFER_INTERNAL,
            EnrollmentApplication.ApplicationType.TRANSFER_EXTERNAL,
        ):
            self.validate_required(data, ["previous_class_id"])

        student_id = data["student_id"]
        class_id = data["class_obj_id"]
        academic_year = int(data["academic_year"])

        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(student_id)) from None

        try:
            class_obj = Class.objects.get(pk=class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None

        if EnrollmentApplication.objects.filter(
            student=student,
            class_obj=class_obj,
            academic_year=academic_year,
            status__in=self.ACTIVE_STATUSES,
        ).exists():
            raise BusinessRuleViolationError(
                "Ja existe uma solicitacao ativa para este aluno nesta turma e ano letivo."
            )

        pending_count = EnrollmentApplication.objects.filter(
            class_obj=class_obj,
            academic_year=academic_year,
            status__in=self.PENDING_STATUSES,
        ).count()
        if (class_obj.enrollment_count + pending_count) >= class_obj.max_students:
            raise BusinessRuleViolationError("Turma sem vagas disponiveis.")

        previous_class = None
        previous_school = ""
        if data.get("previous_class_id"):
            try:
                previous_class = Class.objects.get(pk=data["previous_class_id"])
            except Class.DoesNotExist:
                raise ObjectNotFoundError("Class", str(data["previous_class_id"])) from None
        if data.get("previous_school"):
            previous_school = data["previous_school"].strip()

        application = EnrollmentApplication.objects.create(
            student=student,
            class_obj=class_obj,
            academic_year=academic_year,
            application_number=_generate_application_number(),
            application_type=application_type,
            status=EnrollmentApplication.Status.PRE_ENROLLMENT,
            priority=data.get("priority", 0),
            notes=data.get("notes", ""),
            previous_class=previous_class,
            previous_school=previous_school,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", application)
        self._log(
            "Solicitacao de matricula criada",
            application_id=str(application.pk),
            application_type=application_type,
            student_id=str(student.pk),
            class_id=str(class_obj.pk),
        )
        return application

    def submit_for_review(self, application_id) -> EnrollmentApplication:
        """Envia a pre-matricula para analise."""
        from enrollments.models import EnrollmentApplication

        application = self._get_application(application_id)

        if application.status != EnrollmentApplication.Status.PRE_ENROLLMENT:
            raise BusinessRuleViolationError(
                "Apenas solicitacoes em pre-matricula podem ser enviadas para analise."
            )
        return self._transition_status(
            application,
            EnrollmentApplication.Status.UNDER_REVIEW,
            "Solicitacao enviada para analise",
        )

    def approve_application(self, application_id) -> EnrollmentApplication:
        """Aprova a solicitacao de matricula."""
        from enrollments.models import EnrollmentApplication

        application = self._get_application(application_id)

        if application.status != EnrollmentApplication.Status.UNDER_REVIEW:
            raise BusinessRuleViolationError("Apenas solicitacoes em analise podem ser aprovadas.")

        application.reviewed_by = self.user
        application.reviewed_at = timezone.now()
        return self._transition_status(
            application,
            EnrollmentApplication.Status.APPROVED,
            "Solicitacao aprovada",
            save_fields=["reviewed_by", "reviewed_at"],
        )

    def reject_application(self, application_id, reason: str = "") -> EnrollmentApplication:
        """Recusa a solicitacao de matricula com motivo."""
        from enrollments.models import EnrollmentApplication

        application = self._get_application(application_id)

        if application.status not in (
            EnrollmentApplication.Status.PRE_ENROLLMENT,
            EnrollmentApplication.Status.UNDER_REVIEW,
        ):
            raise BusinessRuleViolationError(
                "Apenas solicitacoes pendentes ou em analise podem ser recusadas."
            )

        application.rejection_reason = (reason or "").strip()
        application.reviewed_by = self.user
        application.reviewed_at = timezone.now()
        return self._transition_status(
            application,
            EnrollmentApplication.Status.REJECTED,
            "Solicitacao recusada",
            save_fields=["rejection_reason", "reviewed_by", "reviewed_at"],
        )

    def request_correction(self, application_id, notes: str = "") -> EnrollmentApplication:
        """Solicita correcoes na documentacao ou dados, voltando para pre-matricula."""
        from enrollments.models import EnrollmentApplication

        application = self._get_application(application_id)

        if application.status != EnrollmentApplication.Status.UNDER_REVIEW:
            raise BusinessRuleViolationError(
                "Apenas solicitacoes em analise podem receber pedido de correcao."
            )

        application.correction_notes = (notes or "").strip()
        return self._transition_status(
            application,
            EnrollmentApplication.Status.PRE_ENROLLMENT,
            "Solicitacao de correcao enviada",
            save_fields=["correction_notes"],
        )

    @transaction.atomic
    def complete_enrollment(self, application_id) -> EnrollmentApplication:
        """Efetiva a matricula — cria o registro em classes.Enrollment."""
        from classes.models import Enrollment
        from enrollments.models import EnrollmentApplication

        application = self._get_application(application_id)

        if application.status != EnrollmentApplication.Status.APPROVED:
            raise BusinessRuleViolationError(
                "Apenas solicitacoes aprovadas podem ser efetivadas como matricula."
            )

        pending_count = (
            EnrollmentApplication.objects.filter(
                class_obj=application.class_obj,
                academic_year=application.academic_year,
                status__in=self.PENDING_STATUSES,
            )
            .exclude(pk=application.pk)
            .count()
        )
        if (
            application.class_obj.enrollment_count + pending_count
        ) >= application.class_obj.max_students:
            raise BusinessRuleViolationError("Turma sem vagas disponiveis.")

        enrollment = Enrollment.objects.create(
            student=application.student,
            class_obj=application.class_obj,
            enrollment_date=timezone.now().date(),
            status=Enrollment.Status.ACTIVE,
            created_by=self.user,
            updated_by=self.user,
        )

        old_status = application.status
        application.status = EnrollmentApplication.Status.ENROLLED
        application.enrollment = enrollment
        application.updated_by = self.user
        application.save(update_fields=["status", "enrollment", "updated_by", "updated_at"])
        self._record_audit("INSERT", enrollment)
        self._record_audit("UPDATE", application, old_values={"status": old_status})
        self._log(
            "Matricula efetivada",
            application_id=str(application.pk),
            enrollment_id=str(enrollment.pk),
            student_id=str(application.student.pk),
            class_id=str(application.class_obj.pk),
        )
        return application

    @transaction.atomic
    def bulk_reenroll(
        self, from_class_id, to_academic_year: int, student_ids: list | None = None
    ) -> int:
        """Rematricula em lote: cria pre-matriculas para alunos de uma turma no novo ano letivo.

        Returns:
            Quantidade de solicitacoes criadas.
        """
        from classes.models import Class, Enrollment
        from enrollments.models import EnrollmentApplication

        try:
            from_class = Class.objects.get(pk=from_class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(from_class_id)) from None

        active_enrollments = Enrollment.objects.filter(
            class_obj=from_class, status=Enrollment.Status.ACTIVE
        ).select_related("student")

        if student_ids:
            active_enrollments = active_enrollments.filter(student_id__in=student_ids)

        count = 0
        for enr in active_enrollments:
            already_exists = EnrollmentApplication.objects.filter(
                student=enr.student,
                academic_year=to_academic_year,
                status__in=self.ACTIVE_STATUSES,
            ).exists()
            if already_exists:
                continue

            app = EnrollmentApplication.objects.create(
                student=enr.student,
                class_obj=from_class,
                academic_year=to_academic_year,
                application_number=_generate_application_number(),
                application_type=EnrollmentApplication.ApplicationType.REENROLL,
                status=EnrollmentApplication.Status.PRE_ENROLLMENT,
                priority=10,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", app)
            count += 1

        self._log(
            "Rematricula em lote concluida",
            from_class_id=str(from_class.pk),
            to_academic_year=str(to_academic_year),
            created_count=str(count),
        )
        return count

    def cancel_application(self, application_id, reason: str = "") -> EnrollmentApplication:
        """Cancela uma solicitacao."""
        from enrollments.models import EnrollmentApplication

        application = self._get_application(application_id)

        if application.status == EnrollmentApplication.Status.CANCELLED:
            raise BusinessRuleViolationError("Solicitacao ja esta cancelada.")

        application.cancellation_reason = (reason or "").strip()
        return self._transition_status(
            application,
            EnrollmentApplication.Status.CANCELLED,
            "Solicitacao cancelada",
            save_fields=["cancellation_reason"],
        )

    def _get_application(self, application_id) -> EnrollmentApplication:
        """Retorna a solicitacao pelo id ou lanca ObjectNotFoundError."""
        from enrollments.models import EnrollmentApplication

        try:
            return EnrollmentApplication.objects.select_related("student", "class_obj").get(
                pk=application_id
            )
        except EnrollmentApplication.DoesNotExist:
            raise ObjectNotFoundError("EnrollmentApplication", str(application_id)) from None

    def _transition_status(
        self,
        application: EnrollmentApplication,
        new_status: str,
        log_message: str,
        save_fields: list[str] | None = None,
    ) -> EnrollmentApplication:
        """Helper DRY: transiciona status, salva, audita e loga em uma unica chamada."""
        old_status = application.status
        application.status = new_status
        application.updated_by = self.user
        fields = ["status", "updated_by", "updated_at"]
        if save_fields:
            fields = fields + save_fields
        application.save(update_fields=fields)
        self._record_audit("UPDATE", application, old_values={"status": old_status})
        self._log(log_message, application_id=str(application.pk))
        return application


class StudentDocumentService(BaseService):
    """Servico de regras de negocio para documentos escolares dos alunos."""

    def add_document(self, data: dict):
        """Adiciona um documento ao checklist do aluno."""
        from enrollments.models import StudentDocument
        from students.models import Student

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
