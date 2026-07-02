"""GuardianService: regras de negócio para responsáveis e vínculos."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from guardians.models import Guardian

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


class _GuardianRepo(BaseRepository):
    """Repositorio de acesso a dados de Guardian."""

    @property
    def model_class(self):
        from guardians.models import Guardian

        return Guardian


class GuardianService(BaseService):
    """Serviço de regras de negócio para responsáveis e vínculos com alunos."""

    def create_guardian(self, data: dict) -> Guardian:
        """Cria um responsável validando usuário, unicidade e registrando auditoria."""
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

        self.validate_required(data, ["relationship_type"])

        cpf_cleaned = self._validate_cpf(data)
        self._validate_rg_state(data)

        guardian = Guardian.objects.create(
            user=user,
            relationship_type=data["relationship_type"],
            birth_date=data.get("birth_date"),
            gender=data.get("gender", Guardian.Gender.NOT_INFORMED),
            nationality=data.get("nationality", "Brasileiro(a)"),
            cpf=cpf_cleaned if cpf_cleaned else "",
            rg_number=data.get("rg_number", ""),
            rg_issuer=data.get("rg_issuer", ""),
            rg_state=data.get("rg_state", ""),
            phone=data.get("phone", ""),
            phone_whatsapp=data.get("phone_whatsapp", ""),
            phone_mobile=data.get("phone_mobile", ""),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", guardian)
        self._log("Responsavel criado", guardian_id=str(guardian.pk))
        return guardian

    def update_guardian(self, guardian_id, data: dict) -> Guardian:
        """Atualiza dados do responsável e registra auditoria com valores antigos."""
        repo = _GuardianRepo()
        guardian = repo.get_by_id(guardian_id)

        old = {"relationship_type": guardian.relationship_type, "cpf": guardian.cpf}

        allowed = {
            "relationship_type",
            "birth_date",
            "gender",
            "nationality",
            "rg_number",
            "rg_issuer",
            "rg_state",
            "phone",
            "phone_whatsapp",
            "phone_mobile",
        }
        updates = {k: v for k, v in data.items() if k in allowed}

        if "cpf" in data:
            cpf_cleaned = self._validate_cpf(data, exclude_id=guardian_id)
            updates["cpf"] = cpf_cleaned if cpf_cleaned else ""

        if "rg_state" in data:
            self._validate_rg_state(data)

        updates["updated_by"] = self.user
        guardian = repo.update(guardian, **updates)
        self._record_audit("UPDATE", guardian, old_values=old)
        self._log("Responsavel atualizado", guardian_id=str(guardian.pk))
        return guardian

    def deactivate_guardian(self, guardian_id) -> Guardian:
        """Aplica exclusão lógica no responsável e registra auditoria."""
        from guardians.models import Guardian

        return self._deactivate(Guardian, guardian_id, "Guardian")

    def link_student(self, guardian_id, student_id, data: dict | None = None):
        """Vincula um aluno a um responsável com metadados (principal, guarda, etc.)."""
        if data is None:
            data = {}
        from guardians.models import Guardian, StudentGuardian
        from students.models import Student

        try:
            guardian = Guardian.objects.get(pk=guardian_id)
        except Guardian.DoesNotExist:
            raise ObjectNotFoundError("Guardian", str(guardian_id)) from None

        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(student_id)) from None

        if StudentGuardian.objects.filter(guardian=guardian, student=student).exists():
            raise BusinessRuleViolationError("Responsável já vinculado a este aluno.")

        link = StudentGuardian.objects.create(
            guardian=guardian,
            student=student,
            is_primary=data.get("is_primary", False),
            has_custody=data.get("has_custody", True),
            can_pickup=data.get("can_pickup", True),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", link)
        self._log("Vinculo aluno-responsavel criado", link_id=str(link.pk))
        return link

    def unlink_student(self, guardian_id, student_id):
        """Remove o vínculo entre responsável e aluno (soft-delete)."""
        from guardians.models import StudentGuardian

        try:
            link = StudentGuardian.objects.get(guardian_id=guardian_id, student_id=student_id)
        except StudentGuardian.DoesNotExist:
            raise ObjectNotFoundError("StudentGuardian", f"{guardian_id}/{student_id}") from None

        if link.is_deleted:
            raise BusinessRuleViolationError("Vínculo já está desativado.")
        link.soft_delete(user=self.user)
        self._record_audit("DELETE", link)
        self._log("Vinculo aluno-responsavel removido", link_id=str(link.pk))
        return link

    def _validate_cpf(self, data: dict, exclude_id=None) -> str | None:
        """Valida CPF: formato e unicidade. Retorna CPF limpo ou None."""
        from base.validators import validate_cpf
        from guardians.models import Guardian

        cpf = data.get("cpf", "")
        if not cpf:
            return None
        try:
            cpf_clean = validate_cpf(cpf)
        except Exception as e:
            raise ValidationError(errors={"cpf": [str(e)]}) from e

        qs = Guardian.objects.filter(cpf=cpf_clean)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise ValidationError(errors={"cpf": ["CPF já cadastrado para outro responsável."]})
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
