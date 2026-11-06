"""ClassService: regras de negócio para turmas e matrículas."""

import logging

from django.utils import timezone

from base.context import require_tenant_schema
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    ValidationError,
)
from base.repositories import BaseRepository
from base.services import BaseService, system_command

logger = logging.getLogger(__name__)


class _ClassRepo(BaseRepository):
    @property
    def model_class(self):
        from classes.contracts import Class

        return Class

    def get_for_update(self, class_id):
        """Retorna a turma ativa sob lock pessimista."""
        try:
            return self.model_class.objects.select_for_update().get(pk=class_id)
        except self.model_class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None


class _EnrollmentRepo(BaseRepository):
    @property
    def model_class(self):
        from classes.contracts import Enrollment

        return Enrollment


class ClassService(BaseService):
    """Serviço de aplicação para o domínio de turmas."""

    @staticmethod
    def _validate_grade_for_stage(grade, education_stage) -> str:
        """Valida e normaliza a série estruturada conforme a etapa."""
        from classes.contracts import GRADES_BY_EDUCATION_STAGE, Class

        grade_value = str(grade or "").strip()
        stage_value = str(education_stage or "").strip()
        valid_grades = {choice.value for choice in Class.Grade}
        if grade_value not in valid_grades:
            raise ValidationError(errors={"grade": ["Selecione uma série válida."]})
        if grade_value not in GRADES_BY_EDUCATION_STAGE.get(stage_value, ()):
            raise ValidationError(
                errors={"grade": ["A série selecionada não pertence à etapa de ensino."]}
            )
        return grade_value

    @staticmethod
    def _validate_shift(shift) -> str:
        """Valida e normaliza o turno aceito pela turma."""
        from classes.contracts import Class

        shift_value = str(shift or "").strip()
        if shift_value not in Class.Shift.values:
            raise ValidationError(errors={"shift": ["Selecione um turno válido."]})
        return shift_value

    def create_class(self, data: dict):
        """Cria uma turma. Não admite (name, academic_year) duplicados."""
        from classes.contracts import Class

        self.validate_required(data, ["name", "education_stage", "grade", "academic_year"])

        year = int(data["academic_year"])
        name = data["name"].strip()
        education_stage = data["education_stage"]
        grade = self._validate_grade_for_stage(data["grade"], education_stage)
        shift = self._validate_shift(data.get("shift", Class.Shift.MORNING))
        if Class.objects.filter(name=name, academic_year=year).exists():
            raise ValidationError(
                errors={"name": ["Já existe turma com este nome neste ano letivo."]}
            )

        class_teacher = None
        if teacher_id := data.get("class_teacher_id"):
            from teachers.contracts import Teacher

            try:
                class_teacher = Teacher.objects.get(pk=teacher_id)
            except Teacher.DoesNotExist:
                raise ObjectNotFoundError("Teacher", str(teacher_id)) from None
        elif "class_teacher" in data:
            # ModelForm entrega a instância de Teacher (ou None).
            class_teacher = data.get("class_teacher")

        cls = Class.objects.create(
            name=name,
            grade=grade,
            education_stage=education_stage,
            shift=shift,
            academic_year=year,
            max_students=int(data.get("max_students", 30) or 30),
            class_teacher=class_teacher,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", cls)
        self._log("Turma criada", class_id=str(cls.pk))
        return cls

    def update_class(self, class_id, data: dict):
        """Atualiza dados de turma existente."""
        repo = _ClassRepo()
        cls = repo.get_for_update(class_id)
        requested_shift = self._validate_shift(data.get("shift", cls.shift))
        if requested_shift != cls.shift:
            from agenda.selectors import ScheduleSelector

            if ScheduleSelector.has_schedule_history(cls.pk):
                raise BusinessRuleViolationError(
                    "O turno da turma não pode ser alterado porque ela possui histórico de grade."
                )
        education_stage = data.get("education_stage", cls.education_stage)
        grade = self._validate_grade_for_stage(data.get("grade", cls.grade), education_stage)
        old = {
            "name": cls.name,
            "grade": cls.grade,
            "education_stage": cls.education_stage,
            "shift": cls.shift,
        }

        allowed = {
            "name",
            "grade",
            "education_stage",
            "shift",
            "max_students",
            "academic_year",
        }
        updates = {k: v for k, v in data.items() if k in allowed}
        updates["grade"] = grade
        updates["shift"] = requested_shift

        if "class_teacher_id" in data:
            from teachers.contracts import Teacher

            teacher_id = data["class_teacher_id"]
            if teacher_id:
                try:
                    updates["class_teacher"] = Teacher.objects.get(pk=teacher_id)
                except Teacher.DoesNotExist:
                    raise ObjectNotFoundError("Teacher", str(teacher_id)) from None
            else:
                updates["class_teacher"] = None

        updates["updated_by"] = self.user
        cls = repo.update(
            cls,
            expected_version=data.get("version", cls.version),
            **updates,
        )
        self._record_audit(
            "UPDATE",
            cls,
            old_values=old,
            new_values=self._snapshot(cls, ["name", "grade", "education_stage", "shift"]),
        )
        self._log("Turma atualizada", class_id=str(cls.pk))
        return cls

    def deactivate_class(self, class_id):
        """Desativa uma turma (soft delete)."""
        from classes.contracts import Class

        return self._deactivate(Class, class_id, "Class")


class AcademicEnrollmentService(BaseService):
    """Porta interna usada exclusivamente pelo workflow de ``enrollments``."""

    @system_command
    def create_from_application(
        self, *, student_id, class_id, academic_year: int, tenant_schema: str
    ):
        """Cria o vínculo final após a aprovação e a conferência documental."""
        schema = require_tenant_schema(tenant_schema)
        from classes.contracts import Class, Enrollment

        student = self._lock_student(student_id)
        try:
            class_obj = Class.objects.select_for_update().get(pk=class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None
        if class_obj.academic_year != int(academic_year):
            raise BusinessRuleViolationError("A turma não pertence ao ano letivo da solicitação.")
        if Enrollment.objects.filter(
            student=student, academic_year=academic_year, status=Enrollment.Status.ACTIVE
        ).exists():
            raise BusinessRuleViolationError("O aluno já possui matrícula ativa neste ano letivo.")
        if (
            Enrollment.objects.filter(class_obj=class_obj, status=Enrollment.Status.ACTIVE).count()
            >= class_obj.max_students
        ):
            raise BusinessRuleViolationError("Turma sem vagas disponíveis.")
        enrollment = Enrollment.objects.create(
            student=student,
            class_obj=class_obj,
            academic_year=academic_year,
            enrollment_date=timezone.localdate(),
            status=Enrollment.Status.ACTIVE,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", enrollment)
        self._log("academic_enrollment_created", enrollment_id=str(enrollment.pk))
        self._sync_activity_submissions(class_obj.pk, schema)
        return enrollment

    @system_command
    def transfer_from_application(
        self, *, source_enrollment_id, target_class_id, reason: str, tenant_schema: str
    ):
        """Encerra a origem como transferida e cria o vínculo ativo de destino."""
        schema = require_tenant_schema(tenant_schema)
        from classes.contracts import Class, Enrollment

        source_student_id = (
            Enrollment.objects.filter(pk=source_enrollment_id)
            .values_list("student_id", flat=True)
            .first()
        )
        if source_student_id is None:
            raise ObjectNotFoundError("Enrollment", str(source_enrollment_id))
        self._lock_student(source_student_id)
        try:
            target = Class.objects.select_for_update().get(pk=target_class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(target_class_id)) from None
        try:
            source = (
                Enrollment.objects.select_for_update()
                .select_related("student")
                .get(pk=source_enrollment_id)
            )
        except Enrollment.DoesNotExist:
            raise ObjectNotFoundError("Enrollment", str(source_enrollment_id)) from None
        if source.status != Enrollment.Status.ACTIVE:
            raise BusinessRuleViolationError("A matrícula de origem não está ativa.")
        clean_reason = self._validate_closure_reason(reason)
        if target.academic_year != source.academic_year:
            raise BusinessRuleViolationError("Transferência interna exige turmas do mesmo ano.")
        if (
            Enrollment.objects.filter(class_obj=target, status=Enrollment.Status.ACTIVE).count()
            >= target.max_students
        ):
            raise BusinessRuleViolationError("Turma de destino sem vagas disponíveis.")
        old = {"status": source.status}
        source.status = Enrollment.Status.TRANSFERRED
        source.cancel_reason = clean_reason
        source.updated_by = self.user
        source.save(update_fields=["status", "cancel_reason", "updated_by", "updated_at"])
        result = Enrollment.objects.create(
            student=source.student,
            class_obj=target,
            academic_year=target.academic_year,
            enrollment_date=timezone.localdate(),
            status=Enrollment.Status.ACTIVE,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("UPDATE", source, old_values=old)
        self._record_audit("INSERT", result)
        self._log(
            "academic_enrollment_transferred",
            source_enrollment_id=str(source.pk),
            result_enrollment_id=str(result.pk),
        )
        self._sync_activity_submissions(source.class_obj_id, schema)
        if target.pk != source.class_obj_id:
            self._sync_activity_submissions(target.pk, schema)
        return result

    @system_command
    def close_from_application(
        self,
        *,
        enrollment_id,
        reason: str,
        tenant_schema: str,
        transferred: bool = False,
    ):
        """Encerra vínculo final preservando todo o histórico acadêmico."""
        schema = require_tenant_schema(tenant_schema)
        from classes.contracts import Enrollment

        try:
            enrollment = Enrollment.objects.select_for_update().get(pk=enrollment_id)
        except Enrollment.DoesNotExist:
            raise ObjectNotFoundError("Enrollment", str(enrollment_id)) from None
        if enrollment.status != Enrollment.Status.ACTIVE:
            raise BusinessRuleViolationError("A matrícula não está ativa.")
        clean_reason = self._validate_closure_reason(reason)
        old = {"status": enrollment.status}
        enrollment.status = (
            Enrollment.Status.TRANSFERRED if transferred else Enrollment.Status.CANCELLED
        )
        enrollment.cancel_reason = clean_reason
        enrollment.updated_by = self.user
        enrollment.save(update_fields=["status", "cancel_reason", "updated_by", "updated_at"])
        self._record_audit("UPDATE", enrollment, old_values=old)
        self._log("academic_enrollment_closed", enrollment_id=str(enrollment.pk))
        self._sync_activity_submissions(enrollment.class_obj_id, schema)
        return enrollment

    def _sync_activity_submissions(self, class_id, tenant_schema: str) -> None:
        """Atualiza projeções de notas no mesmo commit da mudança acadêmica."""
        from activities.services import ActivityService

        ActivityService(user=self.user).sync_class_submissions(
            class_id=class_id,
            tenant_schema=tenant_schema,
        )

    @staticmethod
    def _validate_closure_reason(reason: str) -> str:
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            raise ValidationError(errors={"reason": ["Informe o motivo."]})
        if len(clean_reason) > 200:
            raise ValidationError(
                errors={"reason": ["O motivo deve ter no máximo 200 caracteres."]}
            )
        return clean_reason

    def _lock_student(self, student_id):
        """Bloqueia o aluno antes dos demais agregados, mantendo ordem determinística."""
        from students.contracts import ImportUsageService, Student

        ImportUsageService(user=self.user).seal_for_use(student_ids=[student_id])
        try:
            return Student.objects.select_for_update().get(pk=student_id)
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(student_id)) from None
