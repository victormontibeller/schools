"""StudentService: regras de negócio para alunos."""

import logging

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


class _StudentRepo(BaseRepository):
    @property
    def model_class(self):
        from students.models import Student

        return Student


class StudentService(BaseService):
    """Serviço de regras de negócio para alunos."""

    def create_student(self, data: dict):
        """Cria um aluno validando obrigatórios e matrícula única, registrando auditoria."""
        from students.models import Student

        self.validate_required(data, ["first_name", "last_name", "birth_date", "enrollment_number"])

        enrollment = data["enrollment_number"].strip()
        if Student.objects.filter(enrollment_number=enrollment).exists():
            raise ValidationError(errors={"enrollment_number": ["Matrícula já cadastrada."]})

        student = Student.objects.create(
            first_name=data["first_name"].strip(),
            last_name=data["last_name"].strip(),
            birth_date=data["birth_date"],
            enrollment_number=enrollment,
            gender=data.get("gender", Student.Gender.NOT_INFORMED),
            blood_type=data.get("blood_type", ""),
            special_needs=data.get("special_needs", {}),
            user=data.get("user"),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", student)
        self._log("Aluno criado", student_id=str(student.pk))
        return student

    def update_student(self, student_id, data: dict):
        """Atualiza dados do aluno e registra auditoria com valores antigos."""
        repo = _StudentRepo()
        student = repo.get_by_id(student_id)
        old = {"first_name": student.first_name, "last_name": student.last_name}

        allowed = {"first_name", "last_name", "birth_date", "gender", "blood_type", "special_needs"}
        updates = {k: v for k, v in data.items() if k in allowed}

        if "enrollment_number" in data:
            enrollment = data["enrollment_number"].strip()
            from students.models import Student

            if Student.objects.filter(enrollment_number=enrollment).exclude(pk=student_id).exists():
                raise ValidationError(errors={"enrollment_number": ["Matrícula já cadastrada."]})
            updates["enrollment_number"] = enrollment

        updates["updated_by"] = self.user
        student = repo.update(student, **updates)
        self._record_audit("UPDATE", student, old_values=old)
        return student

    def deactivate_student(self, student_id):
        """Aplica exclusão lógica no aluno e registra auditoria."""
        from students.models import Student

        return self._deactivate(Student, student_id, "Student")

    def restore_student(self, student_id):
        """Reverte a exclusão lógica do aluno e registra auditoria."""
        from students.models import Student

        try:
            student = Student.all_objects.get(pk=student_id)
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(student_id)) from None
        if not student.is_deleted:
            raise BusinessRuleViolationError("Aluno não está desativado.")
        student.restore(user=self.user)
        self._record_audit("RESTORE", student)
        return student
