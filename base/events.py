"""Sistema de eventos in-process."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

logger = logging.getLogger(__name__)


def publish_task_safely(task, *args, tenant_schema: str | None = None, **kwargs) -> bool:
    """Publica uma task sem deixar indisponibilidade do broker escapar após o commit."""
    from base import context

    tenant = tenant_schema or context.current_tenant.get() or "public"
    from base.ports import task_publication_enabled

    if not task_publication_enabled(tenant):
        logger.info(
            "fictitious_task_requires_explicit_drain",
            extra={"tenant": tenant, "task": getattr(task, "name", type(task).__name__)},
        )
        return False
    try:
        task.delay(*args, **kwargs)
    except Exception as exc:
        logger.error(
            "celery_task_publish_failed",
            extra={
                "task": getattr(task, "name", type(task).__name__),
                "tenant": tenant,
                "exception_type": type(exc).__name__,
            },
        )
        return False
    return True


def _publish_task_with_context(
    task,
    args: tuple,
    kwargs: dict,
    tenant_schema: str,
    correlation_id: str,
) -> None:
    """Restaura o contexto capturado antes de publicar a task."""
    from base import context

    tenant_token = context.current_tenant.set(tenant_schema)
    correlation_token = context.correlation_id.set(correlation_id)
    try:
        publish_task_safely(task, *args, tenant_schema=tenant_schema, **kwargs)
    finally:
        context.correlation_id.reset(correlation_token)
        context.current_tenant.reset(tenant_token)


def publish_task_after_commit(
    task,
    *args,
    tenant_schema: str | None = None,
    **kwargs,
) -> None:
    """Registra uma publicação Celery isolada para executar somente após o commit."""
    from django.db import transaction

    from base import context

    tenant = tenant_schema or context.current_tenant.get() or "public"
    callback = partial(
        _publish_task_with_context,
        task,
        args,
        kwargs,
        tenant,
        context.correlation_id.get(),
    )
    transaction.on_commit(callback)


@dataclass
class Event:
    """Evento base carryando o correlation ID da requisição."""

    correlation_id: str = field(default="")


@dataclass
class DomainEvent(Event):
    """Evento emitido por BaseService para toda mutação de domínio.

    Handlers assinam por `operation` (INSERT, UPDATE, DELETE, RESTORE).
    Auditoria, notificações e dashboards podem distinguir por `operation`
    e por `type(instance).__name__` (model_name).
    """

    operation: str = ""
    instance: object = None
    old_values: dict | None = None
    new_values: dict | None = None
    user: object = None


EventHandler = Callable[[Event], None]


class EventDispatcher:
    """Produtores obrigatórios transacionais e observadores opcionais isolados."""

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)
        self._required_handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)

    def register(
        self, event_type: type[Event], handler: EventHandler, *, required: bool = False
    ) -> None:
        """Inscreve produtor obrigatório ou observador opcional para um tipo de evento."""
        registry = self._required_handlers if required else self._handlers
        registry[event_type].append(handler)

    def dispatch(self, event: Event) -> None:
        """Executa obrigatórios primeiro; somente observadores opcionais isolam exceções."""
        # Intenções duráveis pertencem à transação do produtor; falhas devem revertê-la.
        for handler in self._required_handlers.get(type(event), []):
            handler(event)
        for handler in self._handlers.get(type(event), []):
            try:
                handler(event)
            except Exception as exc:
                logger.error(
                    "Event handler failed",
                    extra={
                        "event": type(event).__name__,
                        "handler": handler.__qualname__,
                        "exception_type": type(exc).__name__,
                    },
                )

    def dispatch_type(self, event_type: type[Event], **kwargs) -> None:
        """Constrói e despacha um evento do tipo informado."""
        self.dispatch(event_type(**kwargs))


dispatcher = EventDispatcher()
