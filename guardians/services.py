"""GuardianService: regras de negócio para responsáveis e vínculos com alunos."""

import logging

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


class _GuardianRepo(BaseRepository):
    @property
    def model_class(self):
        from guardians.models import Guardian

        return Guardian


class GuardianService(BaseService):
    """Serviço de regras de negócio para responsáveis e vínculos com alunos."""

    def create_guardian(self, data: dict):
        """Cria um responsável validando usuário e parentesco, e registra auditoria."""
        from guardians.models import Guardian

        user_id = data.get("user_id")
        if not user_id:
            raise ValidationError(errors={"user_id": ["Usuário é obrigatório."]})

        from core.models import CustomUser

        try:
            user = CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            raise ObjectNotFoundError("CustomUser", str(user_id)) from None

        if Guardian.objects.filter(user=user).exists():
            raise BusinessRuleViolationError("Este usuário já possui perfil de responsável.")

        relationship = data.get("relationship_type", "").strip()
        if not relationship:
            raise ValidationError(errors={"relationship_type": ["Parentesco é obrigatório."]})

        guardian = Guardian.objects.create(
            user=user,
            relationship_type=relationship,
            cpf=data.get("cpf", "").strip(),
            rg=data.get("rg", "").strip(),
            phone=data.get("phone", "").strip(),
            phone_whatsapp=data.get("phone_whatsapp", "").strip(),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", guardian)
        self._log("Responsável criado", guardian_id=str(guardian.pk))
        return guardian

    def update_guardian(self, guardian_id, data: dict):
        """Atualiza dados do responsável e registra auditoria com valores antigos."""
        repo = _GuardianRepo()
        guardian = repo.get_by_id(guardian_id)
        old = {"relationship_type": guardian.relationship_type}
        allowed = {"relationship_type", "cpf", "rg", "phone", "phone_whatsapp"}
        updates = {k: v for k, v in data.items() if k in allowed}
        updates["updated_by"] = self.user
        guardian = repo.update(guardian, **updates)
        self._record_audit("UPDATE", guardian, old_values=old)
        return guardian

    def link_student(self, guardian_id, student_id, data: dict = None):
        """Vincula um aluno a um responsável, garantindo único principal, e registra auditoria."""
        from guardians.models import StudentGuardian
        from students.models import Student

        guardian = _GuardianRepo().get_by_id(guardian_id)
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(student_id)) from None

        if StudentGuardian.objects.filter(student=student, guardian=guardian).exists():
            raise BusinessRuleViolationError("Vínculo já existe entre este aluno e responsável.")

        data = data or {}
        is_primary = data.get("is_primary", False)

        # Garante apenas um responsável principal por aluno
        if is_primary:
            StudentGuardian.objects.filter(student=student, is_primary=True).update(
                is_primary=False
            )

        link = StudentGuardian.objects.create(
            student=student,
            guardian=guardian,
            is_primary=is_primary,
            has_custody=data.get("has_custody", True),
            can_pickup=data.get("can_pickup", True),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", link)
        return link

    def unlink_student(self, guardian_id, student_id):
        """Remove o vínculo entre responsável e aluno e loga a operação."""
        from guardians.models import StudentGuardian

        try:
            link = StudentGuardian.objects.get(guardian_id=guardian_id, student_id=student_id)
        except StudentGuardian.DoesNotExist:
            raise ObjectNotFoundError("StudentGuardian", f"{guardian_id}/{student_id}") from None

        link.delete()
        self._log("Vínculo removido", guardian_id=str(guardian_id), student_id=str(student_id))
