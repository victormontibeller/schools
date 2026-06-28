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
