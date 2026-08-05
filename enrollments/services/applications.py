"""Comandos seguros do workflow canônico de solicitações de matrícula."""

from __future__ import annotations

from django.utils import timezone

from base.context import active_tenant_schema
from base.exceptions import BusinessRuleViolationError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService, service_command
from enrollments.services.creation import ApplicationCreationMixin
from enrollments.services.validation import ApplicationValidationMixin


class _ApplicationRepository(BaseRepository):
    """Compare-and-swap de solicitações."""

    @property
    def model_class(self):
        from enrollments.models import EnrollmentApplication

        return EnrollmentApplication


class EnrollmentApplicationService(
    ApplicationValidationMixin, ApplicationCreationMixin, BaseService
):
    """Única fronteira pública para criar e movimentar solicitações."""

    OPEN_STATUSES = (
        "PRE_ENROLLMENT",
        "CORRECTION_REQUIRED",
        "UNDER_REVIEW",
        "WAITLISTED",
        "APPROVED",
    )
    TARGET_TYPES = ("NEW", "REENROLLMENT", "INTERNAL_TRANSFER", "INBOUND_TRANSFER")
    SOURCE_TYPES = ("REENROLLMENT", "INTERNAL_TRANSFER", "OUTBOUND_TRANSFER")
    REASON_REQUIRED_STATUSES = (
        "CORRECTION_REQUIRED",
        "TRANSFERRED",
        "REJECTED",
        "CANCELLED",
    )
    ALLOWED_TRANSITIONS = {
        "PRE_ENROLLMENT": {"UNDER_REVIEW"},
        "CORRECTION_REQUIRED": {"UNDER_REVIEW"},
        "UNDER_REVIEW": {"CORRECTION_REQUIRED", "APPROVED", "WAITLISTED", "REJECTED", "CANCELLED"},
        "WAITLISTED": {"APPROVED", "CORRECTION_REQUIRED", "REJECTED", "CANCELLED"},
        "APPROVED": {"ENROLLED", "TRANSFERRED", "CORRECTION_REQUIRED", "CANCELLED"},
        "ENROLLED": {"TRANSFERRED", "CANCELLED"},
        "TRANSFERRED": set(),
        "REJECTED": set(),
        "CANCELLED": set(),
    }

    @service_command
    def correct_application(self, application_id, data: dict, *, expected_version: int):
        """Corrige dados editáveis antes do reenvio, sem alterar o snapshot documental."""
        from classes.contracts import Class
        from enrollments.models import EnrollmentApplication

        application = self._lock_application(application_id, expected_version)
        if application.status not in {
            EnrollmentApplication.Status.PRE_ENROLLMENT,
            EnrollmentApplication.Status.CORRECTION_REQUIRED,
        }:
            raise BusinessRuleViolationError("A solicitação não está aberta para correção.")
        from classes.contracts import Enrollment

        self._reject_inconsistent_fields(data, application.application_type)
        command_data = {
            **data,
            "target_class_id": data.get("target_class_id", application.target_class_id),
            "source_enrollment_id": data.get(
                "source_enrollment_id", application.source_enrollment_id
            ),
        }
        target = self._resolve_target(command_data, application.application_type, Class)
        source = self._resolve_source(
            command_data, application.application_type, application.student, Enrollment
        )
        notes = str(data.get("notes", application.notes)).strip()
        origin_school = str(data.get("origin_school", application.origin_school)).strip()
        destination_school = str(
            data.get("destination_school", application.destination_school)
        ).strip()
        derived_year = target.academic_year if target else source.academic_year
        if derived_year != application.academic_year:
            raise BusinessRuleViolationError(
                "A correção não pode alterar o ano letivo da solicitação."
            )
        self._validate_type_context(
            application.application_type,
            target_class=target,
            source_enrollment=source,
            origin_school=origin_school,
            destination_school=destination_school,
            notes=notes,
        )
        updates = {
            "target_class": target,
            "source_enrollment": source,
            "origin_school": origin_school,
            "destination_school": destination_school,
            "notes": notes,
            "priority": self._validate_priority(data.get("priority", application.priority)),
            "updated_by": self.user,
        }
        old = self._snapshot(application, [key for key in updates if key != "updated_by"])
        application = _ApplicationRepository().update(
            application, expected_version=expected_version, **updates
        )
        self._record_audit("UPDATE", application, old_values=old)
        self._log("enrollment_application_corrected", application_id=str(application.pk))
        return application

    def submit_application(self, application_id, *, expected_version: int):
        """Envia ou reenvia uma pré-matrícula para análise."""
        from enrollments.models import EnrollmentApplication

        application = self._lock_application(application_id, expected_version)
        if application.status not in {
            EnrollmentApplication.Status.PRE_ENROLLMENT,
            EnrollmentApplication.Status.CORRECTION_REQUIRED,
        }:
            raise BusinessRuleViolationError("A solicitação não pode ser enviada para análise.")
        return self._transition(
            application,
            EnrollmentApplication.Status.UNDER_REVIEW,
            expected_version=expected_version,
        )

    def approve_application(self, application_id, *, expected_version: int):
        """Reserva a vaga ou posiciona a solicitação na lista de espera."""
        from classes.contracts import Enrollment
        from enrollments.models import EnrollmentApplication

        application = self._lock_application(application_id, expected_version)
        if application.status not in {
            EnrollmentApplication.Status.UNDER_REVIEW,
            EnrollmentApplication.Status.WAITLISTED,
        }:
            raise BusinessRuleViolationError("A solicitação não pode ser aprovada neste estado.")
        if application.application_type in {
            EnrollmentApplication.ApplicationType.NEW,
            EnrollmentApplication.ApplicationType.INBOUND_TRANSFER,
            EnrollmentApplication.ApplicationType.REENROLLMENT,
        }:
            self._ensure_no_active_enrollment(application.student_id, application.academic_year)
        target_status = EnrollmentApplication.Status.APPROVED
        extra = {"reviewed_by": self.user, "reviewed_at": timezone.now()}
        if application.target_class_id:
            from classes.contracts import Class

            class_obj = Class.objects.select_for_update().get(pk=application.target_class_id)
            enrolled = Enrollment.objects.filter(
                class_obj=class_obj, status=Enrollment.Status.ACTIVE
            ).count()
            reserved = (
                EnrollmentApplication.objects.filter(
                    target_class=class_obj,
                    status=EnrollmentApplication.Status.APPROVED,
                )
                .exclude(pk=application.pk)
                .count()
            )
            if enrolled + reserved >= class_obj.max_students:
                if application.status == EnrollmentApplication.Status.WAITLISTED:
                    raise BusinessRuleViolationError("A turma continua sem vaga disponível.")
                target_status = EnrollmentApplication.Status.WAITLISTED
                extra["waitlisted_at"] = application.waitlisted_at or timezone.now()
        return self._transition(
            application,
            target_status,
            expected_version=expected_version,
            updates=extra,
        )

    def request_correction(self, application_id, reason: str, *, expected_version: int):
        """Devolve uma solicitação em análise ou aprovada para correção."""
        from enrollments.models import EnrollmentApplication

        application = self._lock_application(application_id, expected_version)
        if application.status not in {
            EnrollmentApplication.Status.UNDER_REVIEW,
            EnrollmentApplication.Status.WAITLISTED,
            EnrollmentApplication.Status.APPROVED,
        }:
            raise BusinessRuleViolationError("A solicitação não pode ser devolvida para correção.")
        return self._transition(
            application,
            EnrollmentApplication.Status.CORRECTION_REQUIRED,
            expected_version=expected_version,
            reason=reason,
        )

    def reject_application(self, application_id, reason: str, *, expected_version: int):
        """Recusa definitivamente solicitação em análise ou espera."""
        from enrollments.models import EnrollmentApplication

        application = self._lock_application(application_id, expected_version)
        if application.status not in {
            EnrollmentApplication.Status.UNDER_REVIEW,
            EnrollmentApplication.Status.WAITLISTED,
        }:
            raise BusinessRuleViolationError("A solicitação não pode ser recusada neste estado.")
        return self._transition(
            application,
            EnrollmentApplication.Status.REJECTED,
            expected_version=expected_version,
            reason=reason,
        )

    @service_command
    def finalize_application(self, application_id, *, expected_version: int, reason: str = ""):
        """Efetiva matrícula ou transferência somente com documentos obrigatórios concluídos."""
        from classes.services import AcademicEnrollmentService
        from enrollments.models import EnrollmentApplication, StudentDocument

        application = self._lock_application(application_id, expected_version)
        if application.status != EnrollmentApplication.Status.APPROVED:
            raise BusinessRuleViolationError("Somente solicitações aprovadas podem ser efetivadas.")
        if (
            StudentDocument.objects.filter(application=application, is_required=True)
            .exclude(status__in=[StudentDocument.Status.VERIFIED, StudentDocument.Status.WAIVED])
            .exists()
        ):
            raise BusinessRuleViolationError(
                "Documentos obrigatórios precisam ser verificados ou dispensados."
            )
        academic_service = AcademicEnrollmentService(user=self.user)
        tenant_schema = active_tenant_schema()
        source_application = None
        is_transfer = application.application_type in {
            EnrollmentApplication.ApplicationType.INTERNAL_TRANSFER,
            EnrollmentApplication.ApplicationType.INBOUND_TRANSFER,
            EnrollmentApplication.ApplicationType.OUTBOUND_TRANSFER,
        }
        transfer_reason = self._required_reason(reason, max_length=200) if is_transfer else ""
        if application.application_type in {
            EnrollmentApplication.ApplicationType.INTERNAL_TRANSFER,
            EnrollmentApplication.ApplicationType.OUTBOUND_TRANSFER,
        }:
            source_application = self._lock_source_application(application.source_enrollment_id)
        if application.application_type == EnrollmentApplication.ApplicationType.OUTBOUND_TRANSFER:
            academic_service.close_from_application(
                enrollment_id=application.source_enrollment_id,
                reason=transfer_reason,
                tenant_schema=tenant_schema,
                transferred=True,
            )
            new_status = EnrollmentApplication.Status.TRANSFERRED
            result = None
        elif (
            application.application_type == EnrollmentApplication.ApplicationType.INTERNAL_TRANSFER
        ):
            result = academic_service.transfer_from_application(
                source_enrollment_id=application.source_enrollment_id,
                target_class_id=application.target_class_id,
                reason=transfer_reason,
                tenant_schema=tenant_schema,
            )
            new_status = EnrollmentApplication.Status.TRANSFERRED
        else:
            result = academic_service.create_from_application(
                student_id=application.student_id,
                class_id=application.target_class_id,
                academic_year=application.academic_year,
                tenant_schema=tenant_schema,
            )
            new_status = EnrollmentApplication.Status.ENROLLED
        updates = {"result_enrollment": result} if result else {}
        application = self._transition(
            application,
            new_status,
            expected_version=expected_version,
            reason=transfer_reason,
            updates=updates,
        )
        if source_application:
            self._transition(
                source_application,
                EnrollmentApplication.Status.TRANSFERRED,
                expected_version=source_application.version,
                reason=transfer_reason,
            )
        return application

    def cancel_application(self, application_id, reason: str, *, expected_version: int):
        """Cancela a solicitação e, quando efetivada, o vínculo acadêmico correspondente."""
        from classes.services import AcademicEnrollmentService
        from enrollments.models import EnrollmentApplication

        application = self._lock_application(application_id, expected_version)
        if EnrollmentApplication.Status.CANCELLED not in self.ALLOWED_TRANSITIONS.get(
            application.status, set()
        ):
            raise BusinessRuleViolationError("A solicitação não pode ser cancelada neste estado.")
        clean_reason = self._required_reason(reason, max_length=200)
        if application.status == EnrollmentApplication.Status.ENROLLED:
            tenant_schema = active_tenant_schema()
            AcademicEnrollmentService(user=self.user).close_from_application(
                enrollment_id=application.result_enrollment_id,
                reason=clean_reason,
                tenant_schema=tenant_schema,
            )
        return self._transition(
            application,
            EnrollmentApplication.Status.CANCELLED,
            expected_version=expected_version,
            reason=clean_reason,
        )

    def _transition(
        self,
        application,
        new_status: str,
        *,
        expected_version: int,
        reason: str = "",
        updates: dict | None = None,
    ):
        """Persiste estado e histórico na mesma transação do comando chamador."""
        from enrollments.models import EnrollmentTransition

        clean_reason = str(reason or "").strip()
        if new_status in self.REASON_REQUIRED_STATUSES:
            clean_reason = self._required_reason(clean_reason)
        old_status = application.status
        if new_status not in self.ALLOWED_TRANSITIONS.get(old_status, set()):
            raise BusinessRuleViolationError("Transição de situação inválida.")
        values = {"status": new_status, "updated_by": self.user, **(updates or {})}
        application = _ApplicationRepository().update(
            application, expected_version=expected_version, **values
        )
        transition = EnrollmentTransition.objects.create(
            application=application,
            from_status=old_status,
            to_status=new_status,
            actor=self.user,
            reason=clean_reason,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("UPDATE", application, old_values={"status": old_status})
        self._record_audit("INSERT", transition)
        self._log(
            "enrollment_application_transitioned",
            application_id=str(application.pk),
            from_status=old_status,
            to_status=new_status,
        )
        return application

    @staticmethod
    def _required_reason(reason: str, *, max_length: int | None = None) -> str:
        clean = str(reason or "").strip()
        if not clean:
            raise ValidationError(errors={"reason": ["Informe o motivo."]})
        if max_length is not None and len(clean) > max_length:
            raise ValidationError(
                errors={"reason": [f"O motivo deve ter no máximo {max_length} caracteres."]}
            )
        return clean
