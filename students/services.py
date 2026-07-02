"""StudentService: regras de negócio para alunos."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from students.models import Student

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


class _StudentRepo(BaseRepository):
    """Repositorio de acesso a dados de Student."""

    @property
    def model_class(self):
        from students.models import Student

        return Student


class StudentService(BaseService):
    """Serviço de regras de negócio para alunos."""

    def create_student(self, data: dict) -> Student:
        """Cria um aluno validando obrigatórios e matrícula única, registrando auditoria."""
        from students.models import Student

        self.validate_required(data, ["first_name", "last_name", "birth_date", "enrollment_number"])

        enrollment = data["enrollment_number"].strip()
        if Student.objects.filter(enrollment_number=enrollment).exists():
            raise ValidationError(errors={"enrollment_number": ["Matrícula já cadastrada."]})

        cpf_cleaned = self._validate_cpf(data)
        self._validate_rg_state(data)

        student = Student.objects.create(
            first_name=data["first_name"].strip(),
            last_name=data["last_name"].strip(),
            birth_date=data["birth_date"],
            enrollment_number=enrollment,
            gender=data.get("gender", Student.Gender.NOT_INFORMED),
            blood_type=data.get("blood_type", ""),
            special_needs=data.get("special_needs", {}),
            user=data.get("user"),
            nationality=data.get("nationality", "Brasileiro(a)"),
            cpf=cpf_cleaned,
            rg_number=data.get("rg_number", ""),
            rg_issuer=data.get("rg_issuer", ""),
            rg_state=data.get("rg_state", ""),
            phone_mobile=data.get("phone_mobile", ""),
            email=data.get("email", ""),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", student)
        self._log("Aluno criado", student_id=str(student.pk))
        return student

    def update_student(self, student_id, data: dict) -> Student:
        """Atualiza dados do aluno e registra auditoria com valores antigos."""
        repo = _StudentRepo()
        student = repo.get_by_id(student_id)
        old = {"first_name": student.first_name, "last_name": student.last_name}

        allowed = {
            "first_name",
            "last_name",
            "birth_date",
            "gender",
            "blood_type",
            "special_needs",
            "nationality",
            "rg_number",
            "rg_issuer",
            "rg_state",
            "phone_mobile",
            "email",
        }
        updates = {k: v for k, v in data.items() if k in allowed}

        if "enrollment_number" in data:
            enrollment = data["enrollment_number"].strip()
            from students.models import Student

            if Student.objects.filter(enrollment_number=enrollment).exclude(pk=student_id).exists():
                raise ValidationError(errors={"enrollment_number": ["Matrícula já cadastrada."]})
            updates["enrollment_number"] = enrollment

        if "cpf" in data:
            cpf_cleaned = self._validate_cpf(data, exclude_id=student_id)
            updates["cpf"] = cpf_cleaned

        if "rg_state" in data:
            self._validate_rg_state(data)

        updates["updated_by"] = self.user
        student = repo.update(student, **updates)
        self._record_audit("UPDATE", student, old_values=old)
        self._log("Aluno atualizado", student_id=str(student.pk))
        return student

    def deactivate_student(self, student_id) -> Student:
        """Aplica exclusão lógica no aluno e registra auditoria."""
        from students.models import Student

        return self._deactivate(Student, student_id, "Student")

    def restore_student(self, student_id) -> Student:
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
        self._log("Aluno restaurado", student_id=str(student.pk))
        return student

    def _validate_cpf(self, data: dict, exclude_id=None) -> str | None:
        """Valida CPF: formato e unicidade. Retorna CPF limpo ou None."""
        from base.validators import validate_cpf
        from students.models import Student

        cpf = data.get("cpf", "")
        if not cpf:
            return None
        try:
            cpf_clean = validate_cpf(cpf)
        except Exception as e:
            raise ValidationError(errors={"cpf": [str(e)]}) from e

        qs = Student.objects.filter(cpf=cpf_clean)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise ValidationError(errors={"cpf": ["CPF já cadastrado para outro aluno."]})
        return cpf_clean

    def _validate_rg_state(self, data: dict) -> None:
        """Valida UF do RG."""
        from base.validators import validate_uf

        rg_state = data.get("rg_state", "")
        if not rg_state:
            return
        try:
            validate_uf(rg_state)
        except Exception as e:
            raise ValidationError(errors={"rg_state": [str(e)]}) from e
