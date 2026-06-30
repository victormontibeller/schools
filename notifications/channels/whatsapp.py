"""Canal de WhatsApp — stub (provedor pendente de integracao).

Para integrar um provedor real (Twilio, Z-API, Meta Cloud API):
    1. Configurar credenciais via settings do Tenant
    2. Implementar `send()` usando o SDK do provedor
    3. Ativar o canal no Admin
"""

from __future__ import annotations

import logging

from notifications.channels.base import BaseChannel, ChannelResult

logger = logging.getLogger(__name__)


class WhatsAppChannel(BaseChannel):
    """Stub do canal WhatsApp — provedor externo pendente."""

    channel_name = "WHATSAPP"

    def send(
        self,
        recipient_address: str,
        subject: str,
        body: str,
        **meta,
    ) -> ChannelResult:
        if not recipient_address:
            return ChannelResult(
                success=False,
                channel=self.channel_name,
                recipient_address="",
                error_message="Telefone nao cadastrado.",
            )

        # TODO: integrar provedor real (Twilio / Z-API / Meta Cloud API)
        # Exemplo com Twilio:
        #   from twilio.rest import Client
        #   client = Client(account_sid, auth_token)
        #   client.messages.create(body=body, from_=from_number, to=recipient_address)
        logger.warning(
            "WhatsApp stub: envio para %s simulado (provedor pendente).",
            recipient_address,
        )

        return ChannelResult(
            success=False,
            channel=self.channel_name,
            recipient_address=recipient_address,
            error_message="Provedor WhatsApp nao configurado (stub).",
        )
