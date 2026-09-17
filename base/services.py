"""BaseService: classe base para todos os serviços de aplicação.

Regra de logs (`docs/04_SECURITY.md` §39): nenhuma informação sensível
(email, senha, CPF, RG, telefone, avatar) poderá aparecer em logs.
O `_log` rejeita chaves de `extra` que parecem PII — falhando cedo em dev
e apenas avisando em prod, para evitar derrubar serviços por log ruidoso.
"""

import logging
import re
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, TypeVar

from base import context

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

logger = logging.getLogger(__name__)
CommandCallable = TypeVar("CommandCallable", bound=Callable)

MUTATION_PREFIXES = (
    "create_",
    "update_",
    "deactivate_",
    "restore_",
    "change_",
    "assign_",
    "remove_",
    "enroll_",
    "transfer_",
    "record_",
    "cancel_",
    "approve_",
    "reject_",
    "submit_",
    "complete_",
    "add_",
    "mark_",
    "send_",
    "generate_",
    "register_",
    "apply_",
    "reconcile_",
    "consume_",
    "expire_",
    "open_",
    "batch_",
    "unenroll_",
    "request_",
    "refresh_",
    "set_",
    "save_",
    "renegotiate_",
    "suspend_",
    "activate_",
    "verify_",
    "bulk_",
    "import_",
    "log_",
)

# Tokens semânticos que tornam uma chave de ``extra`` potencialmente sensível.
_SENSITIVE_LOG_KEY_TOKENS: frozenset[str] = frozenset(
    {
        "address",
        "avatar",
        "birth",
        "birthdate",
        "cellphone",
        "city",
        "complement",
        "content",
        "cpf",
        "description",
        "district",
        "dob",
        "document",
        "email",
        "feedback",
        "justification",
        "message",
        "mobile",
        "name",
        "note",
        "notes",
        "password",
        "phone",
        "reason",
        "recipient",
        "rg",
        "secret",
        "street",
        "telephone",
        "title",
        "token",
        "username",
        "whatsapp",
    }
)

# Fragmentos deliberadamente específicos para grafias concatenadas que a
# tokenização não consegue separar. ``email`` e ``password`` preservam a
# proteção legada por substring; os demais representam aliases pessoais
# conhecidos, sem recorrer a fragmentos amplos como ``name``.
_SENSITIVE_LOG_KEY_FRAGMENTS: tuple[str, ...] = (
    "birthdate",
    "dateofbirth",
    "email",
    "fullname",
    "password",
    "phonenumber",
    "postalcode",
    "profileavatar",
    "recipientaddress",
)

# Exceções opacas e enumeradas. Elas não transportam o dado descrito pelo token:
# identificam tipo/estado técnico, nunca texto fornecido pelo usuário.
_SAFE_TECHNICAL_LOG_KEYS: frozenset[str] = frozenset(
    {
        "channel_name",
        "document_status",
        "event_name",
        "message_log_id",
        "model_name",
        "reason_code",
        "rg_state",
        "role_name",
        "schema_name",
        "secret_rotation_state",
        "task_name",
        "token_count",
    }
)

_CAMEL_ACRONYM_BOUNDARY = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_WORD_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")
_NON_ALNUM_KEY_CHARS = re.compile(r"[^A-Za-z0-9]+")


def _normalize_log_key(key: str) -> str:
    """Normaliza camelCase, acrônimos e separadores para tokens snake_case."""
    separated = _CAMEL_ACRONYM_BOUNDARY.sub(r"\1_\2", key)
    separated = _CAMEL_WORD_BOUNDARY.sub(r"\1_\2", separated)
    return _NON_ALNUM_KEY_CHARS.sub("_", separated).strip("_").casefold()


def _check_no_pii(extra: dict) -> list[str]:
    """Retorna lista de chaves de `extra` que parecem PII (vazão potencia)."""
    leaked: list[str] = []
    for key in extra:
        normalized = _normalize_log_key(key)
        if (
            normalized in _SAFE_TECHNICAL_LOG_KEYS
            or normalized == "id"
            or normalized.endswith("_id")
        ):
            continue
        compact = normalized.replace("_", "")
        if set(normalized.split("_")) & _SENSITIVE_LOG_KEY_TOKENS or any(
            fragment in compact for fragment in _SENSITIVE_LOG_KEY_FRAGMENTS
        ):
            leaked.append(key)
    return leaked


def service_command(method: CommandCallable) -> CommandCallable:
    """Declara um comando de usuário autorizado e transacional."""
    from base.image_services import transactional_image_command

    if getattr(method, "_base_service_atomic", False):
        return method

    @wraps(method)
    def authorized(self, *args, **kwargs):
        from base.exceptions import PermissionDeniedError
        from base.ports import can_execute

        app_label = type(self).__module__.split(".", maxsplit=1)[0]
        if not can_execute(self.user, app_label, method.__name__, type(self).__name__):
            raise PermissionDeniedError("Sem permissão para executar esta operação.")
        return method(self, *args, **kwargs)

    wrapped = transactional_image_command(authorized)
    wrapped._base_service_atomic = True
    wrapped._service_command_kind = "user"
    return wrapped


def system_command(method: CommandCallable) -> CommandCallable:
    """Declara um comando interno transacional sem autorização de usuário."""
    from base.image_services import transactional_image_command

    if getattr(method, "_base_service_atomic", False):
        return method

    wrapped = transactional_image_command(method)
    wrapped._base_service_atomic = True
    wrapped._service_command_kind = "system"
    return wrapped


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

    def _snapshot(self, instance, fields: list[str] | None = None) -> dict:
        """Captura campos concretos para auditoria antes ou depois de uma mutação."""
        snapshot_fields = fields or [field.attname for field in instance._meta.concrete_fields]
        return {
            field: self._audit_value(getattr(instance, field, None)) for field in snapshot_fields
        }

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
        old = self._snapshot(instance)
        instance.soft_delete(user=self.user)
        self._record_audit(
            "DELETE",
            instance,
            old_values=old,
            new_values=self._snapshot(instance),
        )
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
        from base.ports import record_audit

        record_audit(
            user=self.user,
            operation=operation,
            instance=instance,
            old_values=old_values,
            new_values=new_values,
        )
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

    _MUTATION_PREFIXES = MUTATION_PREFIXES

    def __init_subclass__(cls, **kwargs) -> None:
        """Declara comandos nomeados por prefixo como autorizados e atômicos."""
        super().__init_subclass__(**kwargs)

        methods = dict(cls.__dict__)
        for base_class in cls.__mro__[1:]:
            for name, method in base_class.__dict__.items():
                methods.setdefault(name, method)

        for name, method in tuple(methods.items()):
            if not name.startswith(cls._MUTATION_PREFIXES) or not callable(method):
                continue
            if getattr(method, "_base_service_atomic", False):
                continue
            setattr(cls, name, service_command(method))
