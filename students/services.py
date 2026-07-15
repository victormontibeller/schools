"""StudentService: regras de negócio para alunos."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from students.models import Student

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)

STUDENT_REQUIRED_FIELDS = [
    "first_name",
    "last_name",
    "birth_date",
    "gender",
    "blood_type",
    "cpf",
    "rg_number",
    "phone_mobile",
    "email",
]


class _StudentRepo(BaseRepository):
    """Repositorio de acesso a dados de Student."""

    @property
    def model_class(self):
        from students.models import Student

        return Student


class StudentService(BaseService):
    """Serviço de regras de negócio para alunos."""

    @transaction.atomic
    def create_student(self, data: dict) -> Student:
        """Cria um aluno validando obrigatórios e matrícula única, registrando auditoria."""
        from students.models import Student

        self.validate_required(data, STUDENT_REQUIRED_FIELDS)

        from core.services import RegistrationSequenceService

        enrollment = RegistrationSequenceService(user=self.user).next_number("student")
        if Student.objects.filter(enrollment_number=enrollment).exists():
            raise ValidationError(errors={"enrollment_number": ["Matrícula já cadastrada."]})

        cpf_cleaned = self._validate_cpf(data)
        student = Student.objects.create(
            first_name=data["first_name"].strip(),
            last_name=data["last_name"].strip(),
            birth_date=data["birth_date"],
            enrollment_number=enrollment,
            gender=data.get("gender", Student.Gender.NOT_INFORMED),
            blood_type=data.get("blood_type", ""),
            observations=data.get("observations", ""),
            user=data.get("user"),
            cpf=cpf_cleaned,
            rg_number=data.get("rg_number", ""),
            phone_mobile=data.get("phone_mobile", ""),
            email=data.get("email", ""),
            photo=data.get("photo"),
            accepts_email_notifications=bool(data.get("accepts_email_notifications")),
            accepts_whatsapp_notifications=bool(data.get("accepts_whatsapp_notifications")),
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
        old_photo_name = student.photo.name
        photo_storage = student.photo.storage

        # A edição inline pode enviar somente os campos alterados. Valida o
        # estado resultante, não apenas o fragmento submetido.
        validation_data = {
            field: data.get(field, getattr(student, field)) for field in STUDENT_REQUIRED_FIELDS
        }
        self.validate_required(validation_data, STUDENT_REQUIRED_FIELDS)

        allowed = {
            "first_name",
            "last_name",
            "birth_date",
            "gender",
            "blood_type",
            "observations",
            "rg_number",
            "phone_mobile",
            "email",
            "photo",
            "accepts_email_notifications",
            "accepts_whatsapp_notifications",
        }
        old = self._snapshot(student, [*allowed, "enrollment_number", "cpf"])
        updates = {k: v for k, v in data.items() if k in allowed}

        if "cpf" in data:
            from students.models import Student

            cpf_cleaned = self._validate_unique_cpf(
                data,
                Student,
                "CPF já cadastrado para outro aluno.",
                exclude_id=student_id,
            )
            updates["cpf"] = cpf_cleaned

        updates["updated_by"] = self.user
        student = repo.update(
            student,
            expected_version=data.get("version", student.version),
            **updates,
        )
        if "photo" in updates:
            from base.media import delete_replaced_file_after_commit

            delete_replaced_file_after_commit(photo_storage, old_photo_name, student.photo.name)
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
        from students.models import Student

        return self._validate_unique_cpf(
            data,
            Student,
            "CPF já cadastrado para outro aluno.",
            exclude_id=exclude_id,
        )
