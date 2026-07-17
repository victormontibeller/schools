"""Tarefas Celery para cadastro e expiração de contas DEMO."""

from celery import shared_task

from base.context import tenant_schema_context
from notifications.task_helpers import get_transport, retry_email_if_needed


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_demo_verification_task(
    self,
    tenant_schema: str,
    user_id: str,
    verification_url: str,
    message_log_id: str | None = None,
) -> None:
    """Envia confirmação do DEMO usando o SDK de notificações."""
    with tenant_schema_context(tenant_schema):
        from core.contracts import CustomUser
        from notifications.contracts import MessageTemplate

        user = CustomUser.objects.filter(pk=user_id).first()
        if user is None:
            return
        template, _ = MessageTemplate.objects.get_or_create(
            name="demo-email-verification",
            channel=MessageTemplate.Channel.EMAIL,
            defaults={
                "type": MessageTemplate.Type.WELCOME,
                "subject": "Confirme seu acesso à demonstração",
                "body": "Olá, confirme seu acesso por este link: {{ verification_url }}",
            },
        )
        transport = get_transport("EMAIL")
        result = transport.send_individual(
            user,
            template,
            {"verification_url": verification_url},
            message_log_id=message_log_id,
        )
        retry_email_if_needed(self, transport, result)


@shared_task(name="accounts.expire_demo_users")
def expire_demo_users_task(tenant_schema: str = "demo") -> int:
    """Anonimiza contas DEMO vencidas no schema informado."""
    with tenant_schema_context(tenant_schema):
        from accounts.services import AccountService

        return AccountService().expire_demo_users()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_teacher_invitation_task(
    self,
    tenant_schema: str,
    user_id: str,
    invitation_url: str,
    message_log_id: str | None = None,
) -> None:
    """Envia convite do professor pelo transporte centralizado."""
    with tenant_schema_context(tenant_schema):
        from core.contracts import CustomUser
        from notifications.contracts import MessageTemplate

        user = CustomUser.objects.filter(pk=user_id).first()
        if user is None:
            return
        template, _ = MessageTemplate.objects.get_or_create(
            name="teacher-invitation",
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
            message_log_id=message_log_id,
        )
        retry_email_if_needed(self, transport, result)
