"""SMTP exclusivo de recuperação; falha nunca registra a exceção contendo PII/token."""

import logging

from django.core.mail import EmailMultiAlternatives
from django.template import loader

logger = logging.getLogger(__name__)


def send_recovery_email(
    subject_template, body_template, context, from_email, to_email, html_template=None
):
    subject = "".join(loader.render_to_string(subject_template, context).splitlines())
    body = loader.render_to_string(body_template, context)
    from django.conf import settings

    if settings.FICTITIOUS_MODE:
        import uuid

        from base.context import current_tenant
        from notifications.channels.local_fixture import capture_local_message

        capture_local_message(
            recipient=to_email,
            subject=subject,
            body=body,
            identity=f"reset/{uuid.uuid4()}",
            schema=current_tenant.get(),
        )
        return True
    message = EmailMultiAlternatives(subject, body, from_email, [to_email])
    if html_template:
        message.attach_alternative(loader.render_to_string(html_template, context), "text/html")
    try:
        message.send()
    except Exception:
        # SMTP exceptions can embed recipients, full server responses and even the token.
        logger.warning("password_recovery_delivery_failed")
        return False
    return True
