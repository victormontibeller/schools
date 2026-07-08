"""BaseService: classe base para todos os serviços de aplicação.

Regra de logs (`docs/04_SECURITY.md` §39): nenhuma informação sensível
(email, senha, CPF, RG, telefone, avatar) poderá aparecer em logs.
O `_log` rejeita chaves de `extra` que parecem PII — falhando cedo em dev
e apenas avisando em prod, para evitar derrubar serviços por log ruidoso.
"""

import logging
from typing import TYPE_CHECKING

from base import context

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

logger = logging.getLogger(__name__)

# Chaves de `extra` que NUNCA devem carregar PII — ver docs/04_SECURITY.md §39.
_PII_KEYS: frozenset[str] = frozenset(
    {
        "email",
        "password",
        "cpf",
        "rg",
        "phone",
        "phone_whatsapp",
        "user_email",
        "first_name",
        "last_name",
        "address",
        "avatar",
    }
)


def _check_no_pii(extra: dict) -> list[str]:
    """Retorna lista de chaves de `extra` que parecem PII (vazão potencia)."""
    return [k for k in extra if k in _PII_KEYS or "email" in k.lower() or "password" in k.lower()]


class BaseService:
    """Classe base para todos os serviços de aplicação da plataforma."""

    def __init__(self, user: "AbstractBaseUser | None" = None) -> None:
        self.user = user

    # ── Helpers DRY compartilhados ──────────────────────────────────────────

    @staticmethod
    def validate_required(data: dict, fields: list[str]) -> None:
        """Valida que os campos obrigatorios estao presentes e nao vazios.

        Raises:
            ValidationError: com dict de erros por campo.
        """
        from base.exceptions import ValidationError

        errors: dict[str, list[str]] = {}
        for field in fields:
            if data.get(field) in (None, ""):
                errors[field] = ["Campo obrigatorio."]
        if errors:
            raise ValidationError(errors=errors)

    @staticmethod
    def _audit_value(value):
        """Normaliza valores para armazenamento em `AuditLog.old_values`."""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if hasattr(value, "name"):
            return value.name
        if isinstance(value, int | float | bool | str | type(None) | list | dict):
            return value
        return str(value)

    def _snapshot(self, instance, fields: list[str]) -> dict:
        """Captura valores antigos de campos antes de uma mutação."""
        return {field: self._audit_value(getattr(instance, field, None)) for field in fields}

    def _validate_unique_cpf(
        self,
        data: dict,
        model_class,
        duplicate_message: str,
        exclude_id=None,
    ) -> str | None:
        """Valida formato e unicidade de CPF para entidades de pessoa."""
        from base.exceptions import ValidationError
        from base.validators import validate_cpf

        cpf = data.get("cpf", "")
        if not cpf:
            return None
        try:
            cpf_clean = validate_cpf(cpf)
        except Exception as exc:
            raise ValidationError(errors={"cpf": [str(exc)]}) from exc

        qs = model_class.objects.filter(cpf=cpf_clean)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise ValidationError(errors={"cpf": [duplicate_message]})
        return cpf_clean

    def _validate_rg_state(self, data: dict) -> None:
        """Valida a UF do RG quando informada."""
        from base.exceptions import ValidationError
        from base.validators import validate_uf

        rg_state = data.get("rg_state", "")
        if not rg_state:
            return
        try:
            validate_uf(rg_state)
        except Exception as exc:
            raise ValidationError(errors={"rg_state": [str(exc)]}) from exc

    def _person_user_old_values(self, user) -> dict:
        """Captura campos de usuário editados por perfis de pessoa."""
        return self._snapshot(user, ["first_name", "last_name", "avatar"])

    def _person_user_updates(self, data: dict) -> dict:
        """Monta atualizações permitidas para dados básicos do usuário."""
        updates = {"updated_by": self.user}
        if data.get("first_name"):
            updates["first_name"] = data["first_name"].strip()
        if data.get("last_name"):
            updates["last_name"] = data["last_name"].strip()
        avatar = data.get("avatar")
        if avatar:
            updates["avatar"] = avatar
        return updates

    def _deactivate(self, model_class, entity_id, entity_label: str):
        """Soft-delete generico para qualquer modelo de dominio.

        Raises:
            ObjectNotFoundError: se a entidade nao existir.
            BusinessRuleViolationError: se ja estiver desativada.
        """
        from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError

        try:
            instance = model_class.all_objects.get(pk=entity_id)
        except model_class.DoesNotExist:
            raise ObjectNotFoundError(entity_label, str(entity_id)) from None
        if instance.is_deleted:
            raise BusinessRuleViolationError(f"{entity_label} ja esta desativado(a).")
        instance.soft_delete(user=self.user)
        self._record_audit("DELETE", instance)
        self._log("entidade_desativada", entity_type=entity_label, entity_id=str(instance.pk))
        return instance

    # ── Logging e auditoria ─────────────────────────────────────────────────

    def _log(self, message: str, level: str = "info", **extra) -> None:
        # Guarda de PII — docs/04_SECURITY.md §39. Em dev (DEBUG) levanta;
        # em prod apenas descarta a chave e loga warning (não derruba serviço).
        leaked = _check_no_pii(extra)
        if leaked:
            from django.conf import settings

            if getattr(settings, "DEBUG", False):
                raise RuntimeError(
                    f"Tentativa de log PII em {self.__class__.__name__}: {leaked}. "
                    "Ver docs/04_SECURITY.md §39 — nenhum dado sensível em logs."
                )
            logger.warning("PII descartado de log", extra={"leaked_keys": leaked})
            for k in leaked:
                extra.pop(k, None)

        log_data = {
            "service": self.__class__.__name__,
            "user_id": context.user_id.get(),
            "correlation_id": context.correlation_id.get(),
            "tenant": context.current_tenant.get(),
            **extra,
        }
        getattr(logger, level)(message, extra=log_data)

    def _record_audit(
        self,
        operation: str,
        instance,
        old_values: dict | None = None,
        new_values: dict | None = None,
    ) -> None:
        from base.events import DomainEvent, dispatcher

        try:
            dispatcher.dispatch(
                DomainEvent(
                    correlation_id=context.correlation_id.get(),
                    operation=operation,
                    instance=instance,
                    old_values=old_values,
                    new_values=new_values,
                    user=self.user,
                )
            )
        except Exception:
            logger.exception(
                "Audit recording failed",
                extra={"operation": operation, "model": type(instance).__name__},
            )
