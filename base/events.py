"""Sistema de eventos in-process."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


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
    """Despachante de eventos in-process com isolamento de falhas por handler."""

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)

    def register(self, event_type: type[Event], handler: EventHandler) -> None:
        """Inscreve um handler para o tipo de evento informado."""
        self._handlers[event_type].append(handler)

    def dispatch(self, event: Event) -> None:
        """Despacha o evento a todos os handlers inscritos, isolando exceções."""
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
