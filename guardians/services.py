"""GuardianService: regras de negócio para responsáveis e vínculos."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from guardians.models import Guardian

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
from base.repositories import BaseRepository
from base.services import BaseService, service_command

logger = logging.getLogger(__name__)

GUARDIAN_REQUIRED_FIELDS = [
    "first_name",
    "last_name",
    "email",
    "birth_date",
    "gender",
    "cpf",
    "rg_number",
    "phone_mobile",
]
GUARDIAN_EDIT_REQUIRED_FIELDS = GUARDIAN_REQUIRED_FIELDS


class _GuardianRepo(BaseRepository):
    """Repositorio de acesso a dados de Guardian."""

    @property
    def model_class(self):
        from guardians.models import Guardian

        return Guardian


class GuardianService(BaseService):
    """Serviço de regras de negócio para responsáveis e vínculos com alunos."""

    def create_guardian(self, data: dict) -> Guardian:
        """Cria um responsável como contato; a conta é vinculada por fluxo próprio."""
        from guardians.models import Guardian

        data = data.copy()
        self.validate_required(data, GUARDIAN_REQUIRED_FIELDS)

        cpf_cleaned = self._validate_cpf(data)

        guardian = Guardian.objects.create(
            user=None,
            first_name=data["first_name"].strip(),
            last_name=data["last_name"].strip(),
            email=data.get("email", "").strip().lower(),
            avatar=data.get("avatar"),
            birth_date=data.get("birth_date"),
            gender=data.get("gender", Guardian.Gender.NOT_INFORMED),
            cpf=cpf_cleaned if cpf_cleaned else "",
            rg_number=data.get("rg_number", ""),
            rg_issuer=data.get("rg_issuer", ""),
            rg_state=data.get("rg_state", ""),
            phone=data.get("phone", ""),
            phone_whatsapp=data.get("phone_whatsapp", ""),
            phone_mobile=data.get("phone_mobile", ""),
            accepts_email_notifications=bool(data.get("accepts_email_notifications")),
            accepts_whatsapp_notifications=bool(data.get("accepts_whatsapp_notifications")),
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
        old_avatar_name = guardian.avatar.name
        avatar_storage = guardian.avatar.storage

        self.validate_required(data, GUARDIAN_EDIT_REQUIRED_FIELDS)

        allowed = {
            "first_name",
            "last_name",
            "email",
            "avatar",
            "birth_date",
            "gender",
            "cpf",
            "rg_number",
            "phone_mobile",
            "accepts_email_notifications",
            "accepts_whatsapp_notifications",
        }
        old = self._snapshot(guardian, [*allowed, "cpf"])
        updates = {k: v for k, v in data.items() if k in allowed}

        if "cpf" in data:
            cpf_cleaned = self._validate_cpf(data, exclude_id=guardian_id)
            updates["cpf"] = cpf_cleaned if cpf_cleaned else ""

        if "first_name" in updates:
            updates["first_name"] = updates["first_name"].strip()
        if "last_name" in updates:
            updates["last_name"] = updates["last_name"].strip()
        if "email" in updates:
            updates["email"] = updates["email"].strip().lower()

        updates["updated_by"] = self.user
        guardian = repo.update(
            guardian,
            expected_version=data.get("version", guardian.version),
            **updates,
        )
        if "avatar" in updates:
            from base.media import delete_replaced_file_after_commit

            delete_replaced_file_after_commit(avatar_storage, old_avatar_name, guardian.avatar.name)
        self._record_audit("UPDATE", guardian, old_values=old)
        self._log("Responsavel atualizado", guardian_id=str(guardian.pk))
        return guardian

    def deactivate_guardian(self, guardian_id) -> Guardian:
        """Aplica exclusão lógica no responsável e registra auditoria."""
        from guardians.models import Guardian

        return self._deactivate(Guardian, guardian_id, "Guardian")

    @transaction.atomic
    def create_and_link_student(self, student_id, guardian_data: dict, link_data: dict):
        """Cria um contato e o vincula ao aluno na mesma transação."""
        contact_data = guardian_data.copy()
        for field in ("relationship_type", "is_primary", "has_custody", "can_pickup"):
            contact_data.pop(field, None)
        guardian = self.create_guardian(contact_data)
        return self.link_student(guardian.pk, student_id, link_data)

    @service_command
    def link_student(self, guardian_id, student_id, data: dict | None = None):
        """Vincula um aluno a um responsável com metadados (principal, guarda, etc.)."""
        if data is None:
            data = {}
        from guardians.models import Guardian, StudentGuardian
        from students.contracts import Student

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
            relationship_type=data.get("relationship_type", Guardian.Relationship.OTHER),
            created_by=self.user,
            updated_by=self.user,
        )
        if link.is_primary:
            self._clear_other_primaries(student_id, link.pk)
        self._record_audit("INSERT", link)
        self._log("Vinculo aluno-responsavel criado", link_id=str(link.pk))
        return link

    @transaction.atomic
    def update_link(self, link_id, data: dict):
        """Atualiza as permissões e o parentesco de um vínculo."""
        from guardians.models import StudentGuardian

        try:
            link = StudentGuardian.objects.get(pk=link_id)
        except StudentGuardian.DoesNotExist:
            raise ObjectNotFoundError("StudentGuardian", str(link_id)) from None
        self.validate_required(data, ["relationship_type"])
        old = self._snapshot(link, ["relationship_type", "is_primary", "has_custody", "can_pickup"])
        link.relationship_type = data["relationship_type"]
        link.is_primary = bool(data.get("is_primary"))
        link.has_custody = bool(data.get("has_custody"))
        link.can_pickup = bool(data.get("can_pickup"))
        link.updated_by = self.user
        link.save()
        if link.is_primary:
            self._clear_other_primaries(link.student_id, link.pk)
        self._record_audit("UPDATE", link, old_values=old)
        self._log("Vinculo aluno-responsavel atualizado", link_id=str(link.pk))
        return link

    @service_command
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

    def _clear_other_primaries(self, student_id, current_link_id) -> None:
        """Garante no máximo um vínculo principal ativo por aluno."""
        from guardians.models import StudentGuardian

        others = StudentGuardian.objects.filter(student_id=student_id, is_primary=True).exclude(
            pk=current_link_id
        )
        for other in others:
            old = self._snapshot(other, ["is_primary"])
            other.is_primary = False
            other.updated_by = self.user
            other.save(update_fields=["is_primary", "updated_by", "updated_at"])
            self._record_audit("UPDATE", other, old_values=old)

    def _validate_cpf(self, data: dict, exclude_id=None) -> str | None:
        """Valida CPF: formato e unicidade. Retorna CPF limpo ou None."""
        from guardians.models import Guardian

        return self._validate_unique_cpf(
            data,
            Guardian,
            "CPF já cadastrado para outro responsável.",
            exclude_id=exclude_id,
        )
