"""Emissão e consumo atômico de convites, compartilhados entre perfis."""

import uuid
from datetime import timedelta

from django.core import signing
from django.utils import timezone

from base.context import active_tenant_schema
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
from base.services import BaseService, system_command

INVITATION_TTL = 7 * 24 * 60 * 60


class InvitationTokenService(BaseService):
    """Infraestrutura de tokens; emissão é chamada por comandos já autorizados."""

    @system_command
    def issue_token(self, user_id, *, salt: str, extra: dict | None = None) -> str:
        """Rotaciona nonce, invalidando também tarefas e links anteriores."""
        from core.contracts import CustomUser

        schema = active_tenant_schema()
        try:
            user = CustomUser.objects.select_for_update().get(pk=user_id)
        except CustomUser.DoesNotExist:
            raise ObjectNotFoundError("CustomUser", str(user_id)) from None
        if user.is_active or user.email_verified_at:
            raise BusinessRuleViolationError("Esta conta já foi ativada. Utilize recuperar senha.")
        old = self._snapshot(user, ["invitation_sent_at", "invitation_expires_at"])
        user.invitation_nonce = uuid.uuid4()
        user.invitation_sent_at = timezone.now()
        user.invitation_expires_at = timezone.now() + timedelta(seconds=INVITATION_TTL)
        user.updated_by = self.user
        user.save(
            update_fields=[
                "invitation_nonce",
                "invitation_sent_at",
                "invitation_expires_at",
                "updated_by",
            ]
        )
        self._record_audit("UPDATE", user, old_values=old)
        self._log("account_invitation_issued", user_id=str(user.pk))
        token = signing.dumps(
            {
                "user_id": str(user.pk),
                "nonce": str(user.invitation_nonce),
                "schema": schema,
                **(extra or {}),
            },
            salt=salt,
            compress=True,
        )
        from accounts.invitation_selectors import INVITATION_SALTS, InvitationSelector
        from notifications.outbox_services import OutboxService

        kind = next((key for key, value in INVITATION_SALTS.items() if value == salt), None)
        if kind is None:
            raise BusinessRuleViolationError("Tipo de convite indisponível.")
        OutboxService(user=self.user).create_event_deliveries(
            source_type="account_invitation",
            source_id=str(user.pk),
            recipient=user,
            event="account_invitation",
            event_version=str(user.invitation_nonce),
            action_url=InvitationSelector.action_path(kind),
            inbox=False,
            scope={"invitation_kind": kind, "invitation_token": token},
        )
        return token

    @system_command
    def consume_token(self, token: str, password: str, *, salt: str, profile: str = ""):
        """Consome uma única emissão no schema de destino, sem autenticar o usuário."""
        from accounts.services import AccountService
        from core.contracts import CustomUser

        try:
            payload = signing.loads(token, salt=salt, max_age=INVITATION_TTL)
            if not isinstance(payload, dict) or payload.get("schema") != active_tenant_schema():
                raise BusinessRuleViolationError("Convite inválido ou expirado.")
            if profile == "guardian_profile":
                from students.contracts import ImportUsageService

                ImportUsageService().seal_for_use(guardian_ids=[payload.get("guardian_id")])
                from guardians.contracts import Guardian

                if (
                    not Guardian.objects.select_for_update()
                    .filter(pk=payload.get("guardian_id"))
                    .first()
                ):
                    raise BusinessRuleViolationError("Convite inválido ou expirado.")
            user = CustomUser.objects.select_for_update().get(pk=payload.get("user_id"))
        except (signing.BadSignature, CustomUser.DoesNotExist, ValueError, TypeError):
            raise BusinessRuleViolationError("Convite inválido ou expirado.") from None
        from accounts.invitation_selectors import INVITATION_SALTS, InvitationSelector

        kind = next((key for key, value in INVITATION_SALTS.items() if value == salt), None)
        if not InvitationSelector.is_current_token(
            user, token, schema=active_tenant_schema(), kind=kind
        ):
            raise BusinessRuleViolationError("Convite inválido, expirado ou sem acesso vigente.")
        AccountService._validate_password(password, user=user)
        old = self._snapshot(user, ["is_active", "email_verified_at"])
        user.set_password(password)
        user.is_active = True
        user.email_verified_at = timezone.now()
        user.updated_by = user
        user.save()
        self._record_audit("UPDATE", user, old_values=old)
        self._log("account_invitation_accepted", user_id=str(user.pk))
        return user
