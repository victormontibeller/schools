"""Cadastro e convites administrativos, sem senhas provisórias compartilhadas."""

from django.conf import settings
from django.db import connection

from accounts.invitation_tokens import InvitationTokenService
from accounts.user_guards import lock_and_refresh_administrator
from base.context import active_tenant_schema
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import BaseService, system_command

STAFF_INVITE_SALT = "schools.staff-invite.v1"
STAFF_ROLES = {"ADMIN", "SECRETARY", "COORDINATOR", "FINANCE"}


class StaffAccountService(BaseService):
    """Comandos administrativos para colaboradores da escola atual."""

    def create_staff_user(self, data: dict):
        """Cria identidade inativa e agenda convite após a transação."""
        active_tenant_schema()
        lock_and_refresh_administrator(self)
        user = self._create_account(data)
        self._invite(user)
        return user

    def send_staff_invitation(self, user_id):
        """Reenvia convite pendente, revogando o anterior."""
        from core.contracts import CustomUser

        active_tenant_schema()
        lock_and_refresh_administrator(self)
        try:
            user = (
                CustomUser.objects.select_for_update(of=("self",))
                .select_related("role")
                .get(pk=user_id)
            )
        except CustomUser.DoesNotExist:
            raise ObjectNotFoundError("CustomUser", str(user_id)) from None
        if user.role is None or user.role.name not in STAFF_ROLES:
            raise BusinessRuleViolationError(
                "Utilize o convite do cadastro de professor ou responsável."
            )
        return self._invite(user)

    def _create_account(self, data: dict):
        from core.contracts import CustomUser, Role

        self.validate_required(data, ["first_name", "last_name", "email", "role_name"])
        if data["role_name"] not in STAFF_ROLES:
            raise ValidationError(errors={"role_name": ["Selecione um papel administrativo."]})
        email = data["email"].strip().lower()
        if CustomUser.all_objects.filter(email__iexact=email).exists():
            raise ValidationError(errors={"email": ["Este e-mail já possui uma conta."]})
        role = Role.objects.get(name=data["role_name"])
        user = CustomUser.objects.create_user(
            email=email,
            password=None,
            first_name=data["first_name"].strip(),
            last_name=data["last_name"].strip(),
            role=role,
            is_active=False,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", user)
        self._log("staff_account_created", user_id=str(user.pk), role_name=role.name)
        return user

    def _invite(self, user):
        InvitationTokenService(user=self.user).issue_token(user.pk, salt=STAFF_INVITE_SALT)
        return user

    @system_command
    def activate_staff_invitation(self, token: str, password: str):
        """Consome convite público que identifica a escola e a emissão vigente."""
        return InvitationTokenService().consume_token(token, password, salt=STAFF_INVITE_SALT)

    @system_command
    def bootstrap_administrator(self, data: dict, *, tenant_schema: str, existing_user_id=None):
        """Bootstrap interno one-shot chamado pelo provisionamento público autorizado."""
        from core.access.services import AccessConfigurationService
        from core.contracts import CustomUser

        if self.user is not None or active_tenant_schema() != tenant_schema:
            raise BusinessRuleViolationError(
                "Bootstrap exige executor de infraestrutura no tenant."
            )
        if not settings.TESTING and connection.schema_name != tenant_schema:
            raise BusinessRuleViolationError("Schema de bootstrap inválido.")
        AccessConfigurationService().create_missing_access_defaults()
        if existing_user_id:
            try:
                user = CustomUser.objects.get(pk=existing_user_id, role__name="ADMIN")
            except CustomUser.DoesNotExist:
                raise BusinessRuleViolationError(
                    "Bootstrap não corresponde à conta original."
                ) from None
            if CustomUser.all_objects.exclude(pk=user.pk).exists():
                raise BusinessRuleViolationError(
                    "A escola já possui equipe; utilize a administração escolar."
                )
        else:
            if CustomUser.all_objects.exists():
                raise BusinessRuleViolationError(
                    "A escola já possui identidades; bootstrap indisponível."
                )
            user = self._create_account({**data, "role_name": "ADMIN"})
        self._invite(user)
        return user
