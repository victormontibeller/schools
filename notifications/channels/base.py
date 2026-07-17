"""Interface base para canais de envio de mensagens (SDK pattern)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChannelResult:
    """Resultado de um envio por canal."""

    success: bool
    channel: str
    recipient_address: str
    error_message: str = ""
    status_code: int | None = None
    provider_message_id: str = ""
    retryable: bool = False


class BaseChannel(ABC):
    """Interface que todo canal de comunicacao deve implementar.

    Cada canal encapsula seu provedor externo (Resend, futuro provedor WhatsApp, etc.)
    e expoe um unico metodo `send()` com assinatura uniforme.
    """

    channel_name: str = ""

    @abstractmethod
    def send(
        self,
        recipient_address: str,
        subject: str,
        body: str,
        **meta,
    ) -> ChannelResult:
        """Envia a mensagem e retorna o resultado.

        Args:
            recipient_address: e-mail, telefone, ou identificador do destino.
            subject: assunto (ignorado para canais como WhatsApp).
            body: corpo da mensagem renderizada.
            **meta: parametros extras especificos do provedor.

        Returns:
            ChannelResult com status do envio.
        """
        ...
