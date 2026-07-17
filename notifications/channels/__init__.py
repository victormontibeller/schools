"""SDK de canais de comunicacao.

Cada canal implementa a interface `BaseChannel` com o metodo `send()`.
Novos provedores de WhatsApp devem implementar esta interface.
"""

from notifications.channels.base import BaseChannel, ChannelResult
from notifications.channels.email import EmailChannel
from notifications.channels.whatsapp import WhatsAppChannel

__all__ = ["BaseChannel", "ChannelResult", "EmailChannel", "WhatsAppChannel"]
