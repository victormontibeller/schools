"""Preparação e confirmação atômica de rematrícula em lote."""

from uuid import UUID

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import BaseService, service_command


class ReenrollmentService(BaseService):
    """Cria solicitações de rematrícula a partir de um mapeamento confirmado."""

    @service_command
    def confirm_batch(self, mappings: list[dict]):
        """Confirma um único lote aluno–turma, revertendo tudo diante de qualquer erro."""
        from classes.contracts import GRADE_PEDAGOGICAL_ORDER, Class, Enrollment
        from enrollments.models import EnrollmentApplication
        from enrollments.services.applications import EnrollmentApplicationService
        from enrollments.services.validation import ApplicationValidationMixin
        from students.contracts import Student

        if not mappings:
            raise ValidationError(errors={"mappings": ["Selecione ao menos um aluno."]})
        normalized_reasons = []
        for mapping in mappings:
            if not isinstance(mapping, dict):
                raise ValidationError(errors={"mappings": ["Informe um mapeamento válido."]})
            normalized_reasons.append(
                ApplicationValidationMixin._normalize_notes(
                    mapping.get("exception_reason", ""), "exception_reason"
                )
            )
        try:
            source_ids = sorted(
                str(UUID(str(item.get("source_enrollment_id", "")))) for item in mappings
            )
            target_ids = sorted(
                str(UUID(str(item.get("target_class_id", "")))) for item in mappings
            )
        except (TypeError, ValueError, AttributeError):
            raise ValidationError(
                errors={"mappings": ["Informe matrículas de origem e turmas válidas."]}
            ) from None
        if len(source_ids) != len(set(source_ids)):
            raise ValidationError(errors={"mappings": ["A matrícula de origem está duplicada."]})
        source_metadata = list(
            Enrollment.objects.filter(pk__in=source_ids).values("pk", "student_id", "class_obj_id")
        )
        list(
            Student.objects.select_for_update()
            .filter(pk__in=sorted(str(item["student_id"]) for item in source_metadata))
            .order_by("pk")
        )
        class_ids = sorted(
            {
                *target_ids,
                *(str(item["class_obj_id"]) for item in source_metadata),
            }
        )
        locked_classes = Class.objects.select_for_update().filter(pk__in=class_ids).order_by("pk")
        classes = {str(item.pk): item for item in locked_classes}
        sources = {
            str(item.pk): item
            for item in Enrollment.objects.select_for_update()
            .select_related("student", "class_obj")
            .filter(pk__in=source_ids)
            .order_by("pk")
        }
        created = []
        for mapping, exception_reason in zip(mappings, normalized_reasons, strict=True):
            source_id = str(mapping.get("source_enrollment_id", ""))
            target_id = str(mapping.get("target_class_id", ""))
            source = sources.get(source_id)
            target = classes.get(target_id)
            if source is None:
                raise ObjectNotFoundError("Enrollment", source_id)
            if target is None:
                raise ObjectNotFoundError("Class", target_id)
            if source.status != Enrollment.Status.ACTIVE:
                raise BusinessRuleViolationError(
                    "Todas as matrículas de origem devem estar ativas."
                )
            try:
                expected_version = int(mapping["expected_version"])
            except (KeyError, TypeError, ValueError):
                raise ValidationError(
                    errors={"expected_version": ["Versão da matrícula de origem inválida."]}
                ) from None
            if source.version != expected_version:
                raise BusinessRuleViolationError(
                    "Uma matrícula de origem foi alterada. Recarregue o lote e tente novamente."
                )
            if target.academic_year != source.academic_year + 1:
                raise BusinessRuleViolationError("A turma de destino deve ser do ano seguinte.")
            next_grade = None
            try:
                index = GRADE_PEDAGOGICAL_ORDER.index(source.class_obj.grade)
                next_grade = GRADE_PEDAGOGICAL_ORDER[index + 1]
            except (ValueError, IndexError):
                pass
            is_standard_progression = bool(
                next_grade and target.grade == next_grade and target.shift == source.class_obj.shift
            )
            if not is_standard_progression and not exception_reason:
                raise ValidationError(
                    errors={"exception_reason": ["Justifique o destino pedagógico excepcional."]}
                )
            created.append(
                EnrollmentApplicationService(user=self.user)._create_application(
                    {
                        "student_id": source.student_id,
                        "source_enrollment_id": source.pk,
                        "target_class_id": target.pk,
                        "application_type": EnrollmentApplication.ApplicationType.REENROLLMENT,
                        "notes": exception_reason,
                        "priority": 10,
                    }
                )
            )
        self._log("reenrollment_batch_confirmed", created_count=len(created))
        return created
