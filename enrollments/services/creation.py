"""Criação e snapshot inicial de solicitações de matrícula."""

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import service_command


class ApplicationCreationMixin:
    """Implementa o comando de criação exposto pela fachada do workflow."""

    @service_command
    def create_application(self, data: dict, *, expected_version: int = 0):
        """Cria solicitação, deriva o ano e materializa o checklist documental."""
        return self._create_application(data, expected_version=expected_version)

    def _create_application(self, data: dict, *, expected_version: int = 0):
        """Executa a criação dentro de um comando externo já autorizado."""
        from classes.contracts import Class, Enrollment
        from core.services import RegistrationSequenceService
        from enrollments.models import (
            DocumentRequirement,
            EnrollmentApplication,
            EnrollmentTransition,
            StudentDocument,
        )
        from students.contracts import Student

        self.validate_required(data, ["student_id", "application_type"])
        try:
            initial_version = int(expected_version)
        except (TypeError, ValueError):
            raise ValidationError(errors={"expected_version": ["Versão inválida."]}) from None
        if initial_version != 0:
            raise BusinessRuleViolationError("Versão inicial inválida para a solicitação.")
        application_type = data["application_type"]
        if application_type not in EnrollmentApplication.ApplicationType.values:
            raise ValidationError(errors={"application_type": ["Tipo de solicitação inválido."]})
        self._reject_inconsistent_fields(data, application_type)
        try:
            student = Student.objects.select_for_update().get(pk=data["student_id"])
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(data["student_id"])) from None
        target_class = self._resolve_target(data, application_type, Class)
        source_enrollment = self._resolve_source(data, application_type, student, Enrollment)
        academic_year = (
            target_class.academic_year if target_class else source_enrollment.academic_year
        )
        self._validate_type_context(
            application_type,
            target_class=target_class,
            source_enrollment=source_enrollment,
            origin_school=str(data.get("origin_school", "")).strip(),
            destination_school=str(data.get("destination_school", "")).strip(),
            notes=str(data.get("notes", "")).strip(),
        )
        if application_type in {
            EnrollmentApplication.ApplicationType.NEW,
            EnrollmentApplication.ApplicationType.INBOUND_TRANSFER,
            EnrollmentApplication.ApplicationType.REENROLLMENT,
        }:
            self._ensure_no_active_enrollment(student.pk, academic_year)
        if EnrollmentApplication.objects.filter(
            student=student,
            academic_year=academic_year,
            status__in=self.OPEN_STATUSES,
        ).exists():
            raise BusinessRuleViolationError(
                "Já existe uma solicitação aberta para este aluno no ano letivo."
            )
        number = RegistrationSequenceService(user=self.user).next_number(
            "enrollment_application", year=academic_year
        )
        application = EnrollmentApplication.objects.create(
            student=student,
            target_class=target_class,
            source_enrollment=source_enrollment,
            academic_year=academic_year,
            application_number=number,
            application_type=application_type,
            priority=self._validate_priority(data.get("priority", 0)),
            notes=str(data.get("notes", "")).strip(),
            origin_school=str(data.get("origin_school", "")).strip(),
            destination_school=str(data.get("destination_school", "")).strip(),
            created_by=self.user,
            updated_by=self.user,
        )
        transition = EnrollmentTransition.objects.create(
            application=application,
            to_status=EnrollmentApplication.Status.PRE_ENROLLMENT,
            actor=self.user,
            created_by=self.user,
            updated_by=self.user,
        )
        documents = [
            StudentDocument(
                application=application,
                requirement=requirement,
                requirement_code=requirement.code,
                requirement_label=requirement.label,
                is_required=requirement.is_required,
                allows_physical=requirement.allows_physical,
                created_by=self.user,
                updated_by=self.user,
            )
            for requirement in DocumentRequirement.objects.filter(application_type=application_type)
        ]
        if documents:
            StudentDocument.objects.bulk_create(documents)
            for document in documents:
                self._record_audit("INSERT", document)
        self._record_audit("INSERT", application)
        self._record_audit("INSERT", transition)
        self._log(
            "enrollment_application_created",
            application_id=str(application.pk),
            application_type=application_type,
            academic_year=academic_year,
        )
        return application

    def _resolve_target(self, data, application_type, class_model):
        if application_type not in self.TARGET_TYPES:
            return None
        self.validate_required(data, ["target_class_id"])
        try:
            return class_model.objects.select_for_update().get(pk=data["target_class_id"])
        except class_model.DoesNotExist:
            raise ObjectNotFoundError("Class", str(data["target_class_id"])) from None

    def _resolve_source(self, data, application_type, student, enrollment_model):
        if application_type not in self.SOURCE_TYPES:
            return None
        self.validate_required(data, ["source_enrollment_id"])
        try:
            source = (
                enrollment_model.objects.select_for_update()
                .select_related("class_obj")
                .get(pk=data["source_enrollment_id"], student=student)
            )
        except enrollment_model.DoesNotExist:
            raise ObjectNotFoundError("Enrollment", str(data["source_enrollment_id"])) from None
        if source.status != enrollment_model.Status.ACTIVE:
            raise BusinessRuleViolationError("A matrícula de origem não está ativa.")
        return source
