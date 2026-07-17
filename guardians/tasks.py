"""Tarefas tenant-scoped para convites de responsáveis."""

from celery import shared_task

from base.context import tenant_schema_context
from notifications.task_helpers import get_transport, retry_email_if_needed


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_guardian_invitation_task(
    self,
    tenant_schema: str,
    user_id: str,
    invitation_url: str,
    message_log_id: str | None = None,
) -> None:
    """Envia convite transacional pelo transporte centralizado."""
    with tenant_schema_context(tenant_schema):
        from core.contracts import CustomUser
        from notifications.contracts import MessageTemplate

        user = CustomUser.objects.filter(pk=user_id).first()
        if user is None:
            return
        template, _ = MessageTemplate.objects.get_or_create(
            name="guardian-invitation",
            channel=MessageTemplate.Channel.EMAIL,
            defaults={
                "type": MessageTemplate.Type.WELCOME,
                "subject": "Ative seu acesso à escola",
                "body": "Defina sua senha de acesso por este link: {{ invitation_url }}",
            },
        )
        transport = get_transport("EMAIL")
        result = transport.send_individual(
            user,
            template,
            {"invitation_url": invitation_url},
            force=True,
            message_log_id=message_log_id,
        )
        retry_email_if_needed(self, transport, result)
