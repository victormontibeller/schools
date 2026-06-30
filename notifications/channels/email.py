"""Canal de e-mail via SMTP (Django send_mail)."""

from __future__ import annotations

from notifications.channels.base import BaseChannel, ChannelResult


class EmailChannel(BaseChannel):
    """Envio de e-mails usando o backend SMTP configurado no Django.

    O remetente e resolvido por tenant: `School.settings["email"]["from_email"]`
    com fallback para `DEFAULT_FROM_EMAIL` do .env global.
    """

    channel_name = "EMAIL"

    def send(
        self,
        recipient_address: str,
        subject: str,
        body: str,
        **meta,
    ) -> ChannelResult:
        try:
            from django.core.mail import send_mail

            from core.tenant_email import get_tenant_from_email

            from_email = meta.get("from_email") or get_tenant_from_email()
            send_mail(
                subject=subject or "Notificacao",
                message=body,
                from_email=from_email,
                recipient_list=[recipient_address],
                fail_silently=False,
            )
            return ChannelResult(
                success=True, channel=self.channel_name, recipient_address=recipient_address
            )
        except Exception as exc:
            return ChannelResult(
                success=False,
                channel=self.channel_name,
                recipient_address=recipient_address,
                error_message=str(exc),
            )
