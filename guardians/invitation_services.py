"""Convites de acesso para responsáveis já cadastrados pela escola."""

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import BaseService, system_command

GUARDIAN_INVITE_SALT = "schools.guardian-invite.v1"
GUARDIAN_INVITE_TTL_SECONDS = 7 * 24 * 60 * 60


class GuardianInvitationService(BaseService):
    """Cria uma conta inativa e entrega convite assinado de uso único."""

    def send_invitation(self, guardian_id):
        """Prepara a conta e agenda o e-mail após o commit."""
        from core.contracts import CustomUser, Role
        from guardians.models import Guardian
        from students.contracts import ImportUsageService

        ImportUsageService(user=self.user).seal_for_use(guardian_ids=[guardian_id])
        try:
            guardian = Guardian.objects.select_for_update().get(pk=guardian_id)
        except Guardian.DoesNotExist:
            raise ObjectNotFoundError("Guardian", str(guardian_id)) from None
        if not guardian.email:
            raise ValidationError(errors={"email": ["Cadastre um e-mail antes de convidar."]})
        from accounts.invitation_selectors import InvitationSelector

        if not InvitationSelector.guardian_has_custody(guardian.pk):
            raise BusinessRuleViolationError(
                "Acesso digital exige guarda vigente de uma criança ativa."
            )
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
        if user.email.casefold() != guardian.email.strip().casefold():
            raise BusinessRuleViolationError(
                "Corrija o e-mail pelo cadastro da conta antes de reenviar."
            )
        from accounts.invitation_tokens import InvitationTokenService

        InvitationTokenService(user=self.user).issue_token(
            user.pk, salt=GUARDIAN_INVITE_SALT, extra={"guardian_id": str(guardian.pk)}
        )
        self._log("guardian_invitation_sent", guardian_id=str(guardian.pk))
        return user

    @system_command
    def activate_invitation(self, token: str, password: str):
        """Define a senha e consome o convite válido uma única vez."""
        from accounts.invitation_tokens import InvitationTokenService

        return InvitationTokenService().consume_token(
            token, password, salt=GUARDIAN_INVITE_SALT, profile="guardian_profile"
        )
