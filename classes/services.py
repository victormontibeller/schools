"""ClassService: regras de negócio para turmas e matrículas."""

import logging

from django.db import transaction
from django.utils import timezone

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    ValidationError,
)
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


class _ClassRepo(BaseRepository):
    @property
    def model_class(self):
        from classes.models import Class

        return Class


class _EnrollmentRepo(BaseRepository):
    @property
    def model_class(self):
        from classes.models import Enrollment

        return Enrollment


class ClassService(BaseService):
    """Serviço de aplicação para o domínio de turmas."""

    @staticmethod
    def _validate_grade_for_stage(grade, education_stage) -> str:
        """Valida e normaliza a série estruturada conforme a etapa."""
        from classes.models import GRADES_BY_EDUCATION_STAGE, Class

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

    def create_class(self, data: dict):
        """Cria uma turma. Não admite (name, academic_year) duplicados."""
        from classes.models import Class

        self.validate_required(data, ["name", "education_stage", "grade", "academic_year"])

        year = int(data["academic_year"])
        name = data["name"].strip()
        education_stage = data["education_stage"]
        grade = self._validate_grade_for_stage(data["grade"], education_stage)
        if Class.objects.filter(name=name, academic_year=year).exists():
            raise ValidationError(
                errors={"name": ["Já existe turma com este nome neste ano letivo."]}
            )

        class_teacher = None
        if teacher_id := data.get("class_teacher_id"):
            from teachers.models import Teacher

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
            shift=data.get("shift", Class.Shift.MORNING),
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
        cls = repo.get_by_id(class_id)
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

        if "class_teacher_id" in data:
            from teachers.models import Teacher

            teacher_id = data["class_teacher_id"]
            if teacher_id:
                try:
                    updates["class_teacher"] = Teacher.objects.get(pk=teacher_id)
                except Teacher.DoesNotExist:
                    raise ObjectNotFoundError("Teacher", str(teacher_id)) from None
            else:
                updates["class_teacher"] = None

        updates["updated_by"] = self.user
        cls = repo.update(cls, **updates)
        self._record_audit("UPDATE", cls, old_values=old)
        self._log("Turma atualizada", class_id=str(cls.pk))
        return cls

    def deactivate_class(self, class_id):
        """Desativa uma turma (soft delete)."""
        from classes.models import Class

        return self._deactivate(Class, class_id, "Class")

    @transaction.atomic
    def enroll_student(self, class_id, student_id):
        """Matrícula um aluno em uma turma — valida vagas e duplicidade."""
        from classes.models import Enrollment
        from students.models import Student

        cls = _ClassRepo().get_by_id(class_id)
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(student_id)) from None

        if Enrollment.objects.filter(
            student=student, class_obj=cls, status=Enrollment.Status.ACTIVE
        ).exists():
            raise BusinessRuleViolationError("Aluno já matriculado nesta turma.")

        if not cls.has_open_seats:
            raise BusinessRuleViolationError("Turma sem vagas disponíveis.")

        enrollment = Enrollment.objects.create(
            student=student,
            class_obj=cls,
            enrollment_date=timezone.now().date(),
            status=Enrollment.Status.ACTIVE,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", enrollment)
        self._log("Aluno matriculado", class_id=str(cls.pk), student_id=str(student.pk))
        return enrollment

    @transaction.atomic
    def transfer_student(self, student_id, from_class_id, to_class_id):
        """Transfere aluno de uma turma para outra, mantendo histórico."""
        from classes.models import Enrollment
        from students.models import Student

        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(student_id)) from None

        from_class = _ClassRepo().get_by_id(from_class_id)
        to_class = _ClassRepo().get_by_id(to_class_id)

        try:
            active = Enrollment.objects.get(
                student=student, class_obj=from_class, status=Enrollment.Status.ACTIVE
            )
        except Enrollment.DoesNotExist:
            raise BusinessRuleViolationError(
                "Aluno não está matriculado ativamente na turma de origem."
            ) from None

        if Enrollment.objects.filter(
            student=student, class_obj=to_class, status=Enrollment.Status.ACTIVE
        ).exists():
            raise BusinessRuleViolationError("Aluno já está matriculado na turma de destino.")

        if not to_class.has_open_seats:
            raise BusinessRuleViolationError("Turma de destino sem vagas disponíveis.")

        # Cancela a matrícula antiga e cria a nova, preservando histórico.
        active.status = Enrollment.Status.TRANSFERRED
        active.save(update_fields=["status", "updated_at"])

        new = Enrollment.objects.create(
            student=student,
            class_obj=to_class,
            enrollment_date=timezone.now().date(),
            status=Enrollment.Status.ACTIVE,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("UPDATE", active, old_values={"status": "ACTIVE"})
        self._record_audit("INSERT", new)
        self._log(
            "Aluno transferido",
            student_id=str(student.pk),
            from_class=str(from_class.pk),
            to_class=str(to_class.pk),
        )
        return new

    def unenroll_student(self, enrollment_id, reason: str = ""):
        """Cancela uma matrícula ativa com motivo."""
        from classes.models import Enrollment

        try:
            enrollment = Enrollment.objects.get(pk=enrollment_id)
        except Enrollment.DoesNotExist:
            raise ObjectNotFoundError("Enrollment", str(enrollment_id)) from None

        if enrollment.status != Enrollment.Status.ACTIVE:
            raise BusinessRuleViolationError("Matrícula não está ativa.")

        old = {"status": enrollment.status}
        enrollment.status = Enrollment.Status.CANCELLED
        enrollment.cancel_reason = (reason or "").strip()
        enrollment.save(update_fields=["status", "cancel_reason", "updated_at"])
        self._record_audit("UPDATE", enrollment, old_values=old)
        self._log("Aluno desmatriculado", enrollment_id=str(enrollment.pk))
        return enrollment
