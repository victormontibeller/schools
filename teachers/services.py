"""TeacherService: regras de negócio para professores e disciplinas."""

import logging

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


class _SubjectRepo(BaseRepository):
    @property
    def model_class(self):
        from teachers.models import Subject

        return Subject


class _TeacherRepo(BaseRepository):
    @property
    def model_class(self):
        from teachers.models import Teacher

        return Teacher


class TeacherService(BaseService):
    """Serviço de regras de negócio para professores e atribuição de disciplinas."""

    def create_teacher(self, data: dict):
        """Cria um professor validando usuário, matrícula única e registra auditoria."""
        from teachers.models import Teacher

        user_id = data.get("user_id")
        if not user_id:
            raise ValidationError(errors={"user_id": ["Usuário é obrigatório."]})

        from core.models import CustomUser

        try:
            user = CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            raise ObjectNotFoundError("CustomUser", str(user_id)) from None

        if Teacher.objects.filter(user=user).exists():
            raise BusinessRuleViolationError("Este usuário já possui perfil de professor.")

        reg = data.get("registration_number", "").strip()
        if not reg:
            raise ValidationError(errors={"registration_number": ["Matrícula é obrigatória."]})
        if Teacher.objects.filter(registration_number=reg).exists():
            raise ValidationError(errors={"registration_number": ["Matrícula já cadastrada."]})

        teacher = Teacher.objects.create(
            user=user,
            registration_number=reg,
            hire_date=data.get("hire_date"),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", teacher)
        self._log("Professor criado", teacher_id=str(teacher.pk))
        return teacher

    def update_teacher(self, teacher_id, data: dict):
        """Atualiza dados do professor e registra auditoria com valores antigos."""
        repo = _TeacherRepo()
        teacher = repo.get_by_id(teacher_id)
        old = {"registration_number": teacher.registration_number}

        updates = {}
        if "hire_date" in data:
            updates["hire_date"] = data["hire_date"]
        if "registration_number" in data:
            reg = data["registration_number"].strip()
            if not reg:
                raise ValidationError(errors={"registration_number": ["Matrícula é obrigatória."]})
            from teachers.models import Teacher

            if Teacher.objects.filter(registration_number=reg).exclude(pk=teacher_id).exists():
                raise ValidationError(errors={"registration_number": ["Matrícula já cadastrada."]})
            updates["registration_number"] = reg
        updates["updated_by"] = self.user
        teacher = repo.update(teacher, **updates)
        self._record_audit("UPDATE", teacher, old_values=old)
        return teacher

    def deactivate_teacher(self, teacher_id):
        """Aplica exclusão lógica no professor e registra auditoria."""
        from teachers.models import Teacher

        return self._deactivate(Teacher, teacher_id, "Teacher")

    def assign_subject(self, teacher_id, subject_id):
        """Atribui uma disciplina ao professor e registra auditoria."""
        teacher = _TeacherRepo().get_by_id(teacher_id)
        subject = _SubjectRepo().get_by_id(subject_id)
        if teacher.subjects.filter(pk=subject_id).exists():
            raise BusinessRuleViolationError("Disciplina já atribuída ao professor.")
        teacher.subjects.add(subject)
        self._record_audit("UPDATE", teacher)
        return teacher

    def remove_subject(self, teacher_id, subject_id):
        """Remove a disciplina atribuída ao professor e registra auditoria."""
        teacher = _TeacherRepo().get_by_id(teacher_id)
        _SubjectRepo().get_by_id(subject_id)
        teacher.subjects.remove(subject_id)
        self._record_audit("UPDATE", teacher)
        return teacher
