"""Canal de e-mail transacional via Resend API."""

from __future__ import annotations

from notifications.channels.base import BaseChannel, ChannelResult


class EmailChannel(BaseChannel):
    """Envia e-mails com uma chave Resend global e remetente verificado por escola."""

    channel_name = "EMAIL"

    def send(
        self,
        recipient_address: str,
        subject: str,
        body: str,
        **meta,
    ) -> ChannelResult:
        """Envia texto genérico com tags opacas e chave de idempotência."""
        from django.conf import settings

        from core.tenant_email import get_tenant_resend_config

        config = get_tenant_resend_config()
        if not settings.RESEND_API_KEY:
            return self._failure(recipient_address, "provider_not_configured")
        if not config["verified"] or not config["from_email"]:
            return self._failure(recipient_address, "sender_not_verified")

        try:
            import resend
            from resend.exceptions import ResendError
            from resend.http_client_requests import RequestsClient

            resend.api_key = settings.RESEND_API_KEY
            resend.default_http_client = RequestsClient(timeout=settings.RESEND_TIMEOUT_SECONDS)
            sender_name = str(config["school_name"]).strip()
            from_value = (
                f"{sender_name} <{config['from_email']}>" if sender_name else config["from_email"]
            )
            params: resend.Emails.SendParams = {
                "from": str(from_value),
                "to": [recipient_address],
                "subject": subject or "Notificação escolar",
                "text": body,
                "tags": [
                    {"name": "tenant_schema", "value": str(meta["tenant_schema"])},
                    {"name": "message_log_id", "value": str(meta["message_log_id"])},
                    {"name": "category", "value": str(meta.get("category", "notification"))},
                ],
            }
            response = resend.Emails.send(
                params,
                {"idempotency_key": str(meta["idempotency_key"])},
            )
            return ChannelResult(
                success=True,
                channel=self.channel_name,
                recipient_address=recipient_address,
                provider_message_id=str(response["id"]),
                status_code=200,
            )
        except ResendError as exc:
            code = self._status_code(exc.code)
            return self._failure(
                recipient_address,
                f"resend_{exc.error_type}",
                status_code=code,
                retryable=code == 429 or code >= 500,
            )
        except (KeyError, RuntimeError, TimeoutError):
            return self._failure(recipient_address, "provider_unavailable", retryable=True)

    def _failure(
        self,
        recipient_address: str,
        reason: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> ChannelResult:
        """Cria um resultado seguro sem copiar mensagens potencialmente pessoais do provedor."""
        return ChannelResult(
            success=False,
            channel=self.channel_name,
            recipient_address=recipient_address,
            error_message=reason,
            status_code=status_code,
            retryable=retryable,
        )

    @staticmethod
    def _status_code(value) -> int:
        """Normaliza o código HTTP informado pelo SDK."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
