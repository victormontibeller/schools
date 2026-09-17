"""Invariantes compartilhadas dos tipos de solicitação."""

from uuid import UUID

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError


class ApplicationValidationMixin:
    """Valida campos, progressão pedagógica e unicidade acadêmica."""

    @staticmethod
    def _validate_type_context(
        application_type: str,
        *,
        target_class,
        source_enrollment,
        origin_school: str,
        destination_school: str,
        notes: str = "",
    ) -> None:
        from enrollments.models import EnrollmentApplication

        errors = {}
        if (
            application_type == EnrollmentApplication.ApplicationType.INBOUND_TRANSFER
            and not origin_school
        ):
            errors["origin_school"] = ["Informe a escola de origem."]
        if (
            application_type == EnrollmentApplication.ApplicationType.OUTBOUND_TRANSFER
            and not destination_school
        ):
            errors["destination_school"] = ["Informe a escola de destino."]
        if application_type == EnrollmentApplication.ApplicationType.INTERNAL_TRANSFER:
            if source_enrollment.class_obj_id == target_class.pk:
                errors["target_class_id"] = ["A turma de destino deve ser diferente da origem."]
            if source_enrollment.academic_year != target_class.academic_year:
                errors["target_class_id"] = ["Transferência interna exige o mesmo ano letivo."]
        if application_type == EnrollmentApplication.ApplicationType.REENROLLMENT:
            if target_class.academic_year != source_enrollment.academic_year + 1:
                errors["target_class_id"] = ["Rematrícula exige turma do ano letivo seguinte."]
            from classes.contracts import GRADE_PEDAGOGICAL_ORDER

            next_grade = None
            try:
                next_grade = GRADE_PEDAGOGICAL_ORDER[
                    GRADE_PEDAGOGICAL_ORDER.index(source_enrollment.class_obj.grade) + 1
                ]
            except (ValueError, IndexError):
                pass
            is_standard_progression = bool(
                next_grade
                and target_class.grade == next_grade
                and target_class.shift == source_enrollment.class_obj.shift
            )
            if not is_standard_progression and not notes:
                errors["notes"] = ["Justifique o destino pedagógico excepcional."]
        if errors:
            raise ValidationError(errors=errors)

    @staticmethod
    def _reject_inconsistent_fields(data: dict, application_type: str) -> None:
        from enrollments.models import EnrollmentApplication

        allowed = {
            EnrollmentApplication.ApplicationType.NEW: {"target_class_id"},
            EnrollmentApplication.ApplicationType.REENROLLMENT: {
                "target_class_id",
                "source_enrollment_id",
            },
            EnrollmentApplication.ApplicationType.INTERNAL_TRANSFER: {
                "target_class_id",
                "source_enrollment_id",
            },
            EnrollmentApplication.ApplicationType.INBOUND_TRANSFER: {
                "target_class_id",
                "origin_school",
            },
            EnrollmentApplication.ApplicationType.OUTBOUND_TRANSFER: {
                "source_enrollment_id",
                "destination_school",
            },
        }[application_type]
        fields = ("target_class_id", "source_enrollment_id", "origin_school", "destination_school")
        inconsistent = [field for field in fields if data.get(field) and field not in allowed]
        if inconsistent:
            raise ValidationError(
                errors={field: ["Campo incompatível com o tipo."] for field in inconsistent}
            )

    @staticmethod
    def _ensure_no_active_enrollment(student_id, academic_year: int) -> None:
        from classes.contracts import Enrollment

        if Enrollment.objects.filter(
            student_id=student_id,
            academic_year=academic_year,
            status=Enrollment.Status.ACTIVE,
        ).exists():
            raise BusinessRuleViolationError("O aluno já possui matrícula ativa neste ano letivo.")

    @staticmethod
    def _validate_priority(value) -> int:
        """Normaliza a prioridade dentro do limite do campo persistido."""
        try:
            priority = int(value or 0)
        except (TypeError, ValueError):
            raise ValidationError(errors={"priority": ["Prioridade inválida."]}) from None
        if not 0 <= priority <= 32767:
            raise ValidationError(errors={"priority": ["A prioridade deve estar entre 0 e 32767."]})
        return priority

    @staticmethod
    def _normalize_uuid(value, field: str) -> UUID:
        """Converte identificadores externos sem deixar erros do ORM escaparem."""
        try:
            return UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            raise ValidationError(errors={field: ["Identificador inválido."]}) from None

    @staticmethod
    def _normalize_optional_uuid(value, field: str) -> UUID | None:
        """Normaliza UUID opcional preservando ausência como ``None``."""
        return ApplicationValidationMixin._normalize_uuid(value, field) if value else None

    @staticmethod
    def _normalize_school(value, field: str) -> str:
        """Normaliza nomes de escola dentro do limite do schema persistido."""
        school = str(value or "").strip()
        if len(school) > 200:
            raise ValidationError(errors={field: ["Informe no máximo 200 caracteres."]})
        return school

    @staticmethod
    def _normalize_notes(value, field: str = "notes") -> str:
        """Normaliza observações e justificativas dentro do limite persistido."""
        notes = str(value or "").strip()
        if len(notes) > 1000:
            raise ValidationError(errors={field: ["Informe no máximo 1000 caracteres."]})
        return notes

    @staticmethod
    def _lock_application(application_id, expected_version: int):
        """Bloqueia aluno e solicitação antes de validar a versão otimista."""
        from enrollments.models import EnrollmentApplication
        from students.contracts import Student

        try:
            expected = int(expected_version)
        except (TypeError, ValueError):
            raise ValidationError(errors={"expected_version": ["Versão inválida."]}) from None
        normalized_application_id = ApplicationValidationMixin._normalize_uuid(
            application_id, "application_id"
        )
        student_id = (
            EnrollmentApplication.objects.filter(pk=normalized_application_id)
            .values_list("student_id", flat=True)
            .first()
        )
        if student_id is None:
            raise ObjectNotFoundError("EnrollmentApplication", str(application_id))
        Student.objects.select_for_update().get(pk=student_id)
        try:
            application = EnrollmentApplication.objects.select_for_update().get(
                pk=normalized_application_id
            )
        except EnrollmentApplication.DoesNotExist:
            raise ObjectNotFoundError("EnrollmentApplication", str(application_id)) from None
        if application.version != expected:
            raise BusinessRuleViolationError(
                "Este registro foi alterado por outra pessoa. "
                "Recarregue os dados e tente novamente."
            )
        return application

    @staticmethod
    def _lock_source_application(enrollment_id):
        """Bloqueia a solicitação que originou o vínculo, quando ela existir."""
        from enrollments.models import EnrollmentApplication

        return (
            EnrollmentApplication.objects.select_for_update()
            .filter(
                result_enrollment_id=enrollment_id,
                status=EnrollmentApplication.Status.ENROLLED,
            )
            .first()
        )
