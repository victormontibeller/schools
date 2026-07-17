"""Convites de acesso para responsáveis já cadastrados pela escola."""

from django.core import signing
from django.db import connection, transaction
from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import BaseService

GUARDIAN_INVITE_SALT = "schools.guardian-invite.v1"
GUARDIAN_INVITE_TTL_SECONDS = 7 * 24 * 60 * 60


class GuardianInvitationService(BaseService):
    """Cria uma conta inativa e entrega convite assinado de uso único."""

    def send_invitation(self, guardian_id, invitation_url_builder):
        """Prepara a conta e agenda o e-mail após o commit."""
        from core.contracts import CustomUser, Role
        from guardians.models import Guardian

        try:
            guardian = Guardian.objects.select_for_update().get(pk=guardian_id)
        except Guardian.DoesNotExist:
            raise ObjectNotFoundError("Guardian", str(guardian_id)) from None
        if not guardian.email:
            raise ValidationError(errors={"email": ["Cadastre um e-mail antes de convidar."]})
        if guardian.user_id and (guardian.user.is_active or guardian.user.email_verified_at):
            raise BusinessRuleViolationError("Este responsável já possui acesso ativo.")
        user = guardian.user
        if user is None:
            email = guardian.email.strip().lower()
            if CustomUser.all_objects.filter(email__iexact=email, deleted_at__isnull=True).exists():
                raise BusinessRuleViolationError("Já existe uma conta com este e-mail.")
            try:
                role = Role.objects.get(name=Role.Name.GUARDIAN)
            except Role.DoesNotExist:
                raise ObjectNotFoundError("Role", Role.Name.GUARDIAN) from None
            user = CustomUser.objects.create_user(
                email=email,
                password=None,
                first_name=guardian.first_name,
                last_name=guardian.last_name,
                role=role,
                is_active=False,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", user)
            old = self._snapshot(guardian, ["user_id"])
            guardian.user = user
            guardian.updated_by = self.user
            guardian.save(update_fields=["user", "updated_by", "updated_at"])
            self._record_audit("UPDATE", guardian, old_values=old)
        token = signing.dumps(
            {"user_id": str(user.pk), "guardian_id": str(guardian.pk)},
            salt=GUARDIAN_INVITE_SALT,
            compress=True,
        )
        invitation_url = invitation_url_builder(token)
        from guardians.tasks import send_guardian_invitation_task

        schema_name = getattr(connection, "schema_name", "public")
        transaction.on_commit(
            lambda: send_guardian_invitation_task.delay(schema_name, str(user.pk), invitation_url)
        )
        self._log("guardian_invitation_sent", guardian_id=str(guardian.pk))
        return user

    def activate_invitation(self, token: str, password: str):
        """Define a senha e consome o convite válido uma única vez."""
        from accounts.services import AccountService
        from core.contracts import CustomUser
        from guardians.models import Guardian

        try:
            payload = signing.loads(
                token, salt=GUARDIAN_INVITE_SALT, max_age=GUARDIAN_INVITE_TTL_SECONDS
            )
        except signing.BadSignature as exc:
            raise BusinessRuleViolationError("Convite inválido ou expirado.") from exc
        try:
            user = CustomUser.all_objects.get(pk=payload.get("user_id"), deleted_at__isnull=True)
            Guardian.objects.get(pk=payload.get("guardian_id"), user=user)
        except (CustomUser.DoesNotExist, Guardian.DoesNotExist):
            raise BusinessRuleViolationError("Convite inválido ou expirado.") from None
        if user.is_active or user.email_verified_at:
            raise BusinessRuleViolationError("Este convite já foi utilizado.")
        AccountService._validate_password(password, user=user)
        old = self._snapshot(user, ["is_active", "email_verified_at"])
        user.set_password(password)
        user.is_active = True
        user.email_verified_at = timezone.now()
        user.updated_by = user
        user.save()
        self._record_audit("UPDATE", user, old_values=old)
        self._log("guardian_invitation_accepted", guardian_id=str(payload["guardian_id"]))
        return user
