"""Comandos seguros do checklist documental de matrículas."""

from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.services import BaseService, service_command


class StudentDocumentService(BaseService):
    """Registra entrega, conferência, recusa e dispensa de documentos."""

    @service_command
    def create_requirement(self, data: dict, *, expected_version: int = 0):
        """Configura um requisito futuro conforme a capacidade independente."""
        from enrollments.models import DocumentRequirement, EnrollmentApplication

        try:
            initial_version = int(expected_version)
        except (TypeError, ValueError):
            raise ValidationError(errors={"expected_version": ["Versão inválida."]}) from None
        if initial_version != 0:
            raise BusinessRuleViolationError("Versão inicial inválida para o requisito.")
        self.validate_required(data, ["application_type", "code", "label"])
        if data["application_type"] not in EnrollmentApplication.ApplicationType.values:
            raise ValidationError(errors={"application_type": ["Tipo inválido."]})
        code = self._normalize_requirement_code(data["code"])
        label = str(data["label"]).strip()
        if not label:
            raise ValidationError(errors={"label": ["Campo obrigatório."]})
        if len(label) > 120:
            raise ValidationError(errors={"label": ["Informe no máximo 120 caracteres."]})
        if DocumentRequirement.objects.filter(
            application_type=data["application_type"], code=code
        ).exists():
            raise ValidationError(errors={"code": ["Requisito já cadastrado para este tipo."]})
        try:
            with transaction.atomic():
                requirement = DocumentRequirement.objects.create(
                    application_type=data["application_type"],
                    code=code,
                    label=label,
                    is_required=bool(data.get("is_required", True)),
                    allows_physical=bool(data.get("allows_physical", False)),
                    display_order=self._validate_display_order(data.get("display_order", 0)),
                    created_by=self.user,
                    updated_by=self.user,
                )
        except IntegrityError:
            raise ValidationError(
                errors={"code": ["Requisito já cadastrado para este tipo."]}
            ) from None
        self._record_audit("INSERT", requirement, new_values=self._snapshot(requirement))
        self._log("document_requirement_created", requirement_id=str(requirement.pk))
        return requirement

    @service_command
    def update_requirement(self, requirement_id, data: dict, *, expected_version: int):
        """Altera somente requisitos futuros, sem tocar snapshots já materializados."""
        from enrollments.models import DocumentRequirement, EnrollmentApplication

        requirement = self._lock_requirement(requirement_id, expected_version)
        application_type = data.get("application_type", requirement.application_type)
        if application_type not in EnrollmentApplication.ApplicationType.values:
            raise ValidationError(errors={"application_type": ["Tipo inválido."]})
        code = self._normalize_requirement_code(data.get("code", requirement.code))
        label = str(data.get("label", requirement.label)).strip()
        if not label:
            raise ValidationError(errors={"label": ["Campo obrigatório."]})
        if len(label) > 120:
            raise ValidationError(errors={"label": ["Informe no máximo 120 caracteres."]})
        if (
            DocumentRequirement.objects.filter(application_type=application_type, code=code)
            .exclude(pk=requirement.pk)
            .exists()
        ):
            raise ValidationError(errors={"code": ["Requisito já cadastrado para este tipo."]})
        updates = {
            "application_type": application_type,
            "code": code,
            "label": label,
            "is_required": bool(data.get("is_required", requirement.is_required)),
            "allows_physical": bool(data.get("allows_physical", requirement.allows_physical)),
            "display_order": self._validate_display_order(
                data.get("display_order", requirement.display_order)
            ),
            "updated_by": self.user,
        }
        old = self._snapshot(requirement)
        for field, value in updates.items():
            setattr(requirement, field, value)
        try:
            with transaction.atomic():
                requirement.save(update_fields=[*updates, "updated_at"])
        except IntegrityError:
            raise ValidationError(
                errors={"code": ["Requisito já cadastrado para este tipo."]}
            ) from None
        self._record_audit(
            "UPDATE",
            requirement,
            old_values=old,
            new_values=self._snapshot(requirement),
        )
        self._log("document_requirement_updated", requirement_id=str(requirement.pk))
        return requirement

    @service_command
    def deactivate_requirement(self, requirement_id, *, expected_version: int):
        """Desativa requisito futuro preservando snapshots existentes."""
        from enrollments.models import DocumentRequirement

        self._lock_requirement(requirement_id, expected_version)
        return self._deactivate(DocumentRequirement, requirement_id, "DocumentRequirement")

    def record_delivery(
        self,
        document_id,
        *,
        delivery_method: str,
        file=None,
        expected_version: int,
    ):
        """Registra entrega digital ou conferência física preservando o upload."""
        from enrollments.models import StudentDocument

        document = self._lock_document(document_id, expected_version)
        if document.status in {StudentDocument.Status.VERIFIED, StudentDocument.Status.WAIVED}:
            raise BusinessRuleViolationError("Documento concluído não pode ser entregue novamente.")
        if delivery_method not in StudentDocument.DeliveryMethod.values:
            raise ValidationError(errors={"delivery_method": ["Forma de entrega inválida."]})
        if delivery_method == StudentDocument.DeliveryMethod.PHYSICAL:
            if not document.allows_physical:
                raise BusinessRuleViolationError("Este requisito não aceita entrega física.")
            if file:
                raise ValidationError(errors={"file": ["Entrega física não recebe arquivo."]})
        elif not file:
            raise ValidationError(errors={"file": ["Selecione o arquivo entregue."]})
        if file:
            from django.core.exceptions import ValidationError as DjangoValidationError

            from base.upload_validators import validate_document_upload

            try:
                validate_document_upload(file)
            except DjangoValidationError as exc:
                raise ValidationError(errors={"file": list(exc.messages)}) from exc
        old = self._snapshot(document)
        old_file_name = document.file.name
        storage = document.file.storage
        updates = {
            "status": StudentDocument.Status.SUBMITTED,
            "delivery_method": delivery_method,
            "decision_reason": "",
            "verified_by": None,
            "verified_at": None,
            "updated_by": self.user,
        }
        new_file_name = ""
        try:
            if file:
                document.file.save(file.name, file, save=False)
                new_file_name = document.file.name
                updates["file"] = new_file_name
            elif delivery_method == StudentDocument.DeliveryMethod.PHYSICAL:
                updates["file"] = None
            document = self._save_locked_document(document, updates)
            self._record_audit(
                "UPDATE",
                document,
                old_values=old,
                new_values=self._snapshot(document),
            )
        except Exception:
            if new_file_name and new_file_name != old_file_name:
                storage.delete(new_file_name)
            raise
        from base.media import delete_replaced_file_after_commit

        delete_replaced_file_after_commit(storage, old_file_name, document.file.name)
        self._log("student_document_submitted", document_id=str(document.pk))
        return document

    def verify_document(self, document_id, *, expected_version: int):
        """Confirma documento previamente entregue."""
        from enrollments.models import StudentDocument

        document = self._lock_document(document_id, expected_version)
        if document.status != StudentDocument.Status.SUBMITTED:
            raise BusinessRuleViolationError("Somente documento entregue pode ser verificado.")
        return self._decide(
            document,
            StudentDocument.Status.VERIFIED,
            expected_version=expected_version,
        )

    def reject_document(self, document_id, reason: str, *, expected_version: int):
        """Recusa documento entregue com motivo obrigatório."""
        from enrollments.models import StudentDocument

        document = self._lock_document(document_id, expected_version)
        if document.status != StudentDocument.Status.SUBMITTED:
            raise BusinessRuleViolationError("Somente documento entregue pode ser recusado.")
        return self._decide(
            document,
            StudentDocument.Status.REJECTED,
            expected_version=expected_version,
            reason=self._required_reason(reason),
        )

    @service_command
    def waive_document(self, document_id, reason: str, *, expected_version: int):
        """Dispensa requisito com motivo; operação exclusiva de Administrador."""
        from enrollments.models import StudentDocument

        self._require_admin("dispensar documentos")
        document = self._lock_document(document_id, expected_version)
        if document.status in {StudentDocument.Status.VERIFIED, StudentDocument.Status.WAIVED}:
            raise BusinessRuleViolationError("Documento concluído não pode ser dispensado.")
        return self._decide(
            document,
            StudentDocument.Status.WAIVED,
            expected_version=expected_version,
            reason=self._required_reason(reason),
        )

    def _decide(
        self,
        document,
        status: str,
        *,
        expected_version: int,
        reason: str = "",
    ):
        old = self._snapshot(document)
        document = self._save_locked_document(
            document,
            {
                "status": status,
                "decision_reason": reason,
                "verified_by": self.user,
                "verified_at": timezone.now(),
                "updated_by": self.user,
            },
        )
        self._record_audit(
            "UPDATE",
            document,
            old_values=old,
            new_values=self._snapshot(document),
        )
        self._log(
            "student_document_decided",
            document_id=str(document.pk),
            document_status=status,
        )
        return document

    @staticmethod
    def _save_locked_document(document, updates: dict):
        """Persiste por ``Model.save`` após o lock, incluindo a versão otimista."""
        for field, value in updates.items():
            setattr(document, field, value)
        document.save(update_fields=[*updates, "updated_at"])
        return document

    @staticmethod
    def _lock_document(document_id, expected_version: int):
        from enrollments.models import StudentDocument

        normalized_document_id = StudentDocumentService._normalize_uuid(document_id, "document_id")
        try:
            expected = int(expected_version)
        except (TypeError, ValueError):
            raise ValidationError(errors={"expected_version": ["Versão inválida."]}) from None
        try:
            document = StudentDocument.objects.select_for_update().get(pk=normalized_document_id)
        except StudentDocument.DoesNotExist:
            raise ObjectNotFoundError("StudentDocument", str(document_id)) from None
        if document.version != expected:
            raise BusinessRuleViolationError(
                "Este registro foi alterado por outra pessoa. Recarregue e tente novamente."
            )
        return document

    @staticmethod
    def _lock_requirement(requirement_id, expected_version: int):
        from enrollments.models import DocumentRequirement

        normalized_requirement_id = StudentDocumentService._normalize_uuid(
            requirement_id, "requirement_id"
        )
        try:
            expected = int(expected_version)
        except (TypeError, ValueError):
            raise ValidationError(errors={"expected_version": ["Versão inválida."]}) from None
        try:
            requirement = DocumentRequirement.objects.select_for_update().get(
                pk=normalized_requirement_id
            )
        except DocumentRequirement.DoesNotExist:
            raise ObjectNotFoundError("DocumentRequirement", str(requirement_id)) from None
        if requirement.version != expected:
            raise BusinessRuleViolationError(
                "Este registro foi alterado por outra pessoa. Recarregue e tente novamente."
            )
        return requirement

    def _require_admin(self, action: str) -> None:
        from core.access_catalog import ADMIN
        from core.permissions import role_name

        if not getattr(self.user, "is_superuser", False) and role_name(self.user) != ADMIN:
            raise PermissionDeniedError(f"Somente Administrador pode {action}.")

    @staticmethod
    def _normalize_requirement_code(value) -> str:
        from django.utils.text import slugify

        code = slugify(str(value or "").strip())
        if not code:
            raise ValidationError(errors={"code": ["Informe um código válido."]})
        if len(code) > 50:
            raise ValidationError(errors={"code": ["O código deve ter até 50 caracteres."]})
        return code

    @staticmethod
    def _validate_display_order(value) -> int:
        try:
            display_order = int(value or 0)
        except (TypeError, ValueError):
            raise ValidationError(errors={"display_order": ["Ordem inválida."]}) from None
        if not 0 <= display_order <= 32767:
            raise ValidationError(errors={"display_order": ["A ordem deve estar entre 0 e 32767."]})
        return display_order

    @staticmethod
    def _required_reason(reason: str) -> str:
        clean = str(reason or "").strip()
        if not clean:
            raise ValidationError(errors={"reason": ["Informe o motivo."]})
        return clean

    @staticmethod
    def _normalize_uuid(value, field: str) -> UUID:
        """Converte identificadores externos em erros de validação do domínio."""
        try:
            return UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            raise ValidationError(errors={field: ["Identificador inválido."]}) from None
