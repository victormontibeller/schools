"""Confirmação auditada de recuperação, com token revalidado sob lock."""

from django.conf import settings
from django.db import connection

from accounts.recovery_tokens import recovery_token_generator
from accounts.services import AccountService
from base.context import current_tenant
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
from base.services import BaseService, system_command


class PasswordRecoveryService(BaseService):
    @system_command
    def confirm_password_reset(self, *, user_id, token, password, schema_name):
        from core.contracts import CustomUser
        from tenancy.selectors import SchoolSelector

        invalid = "O link não está disponível. Solicite uma nova recuperação de acesso."
        if not schema_name or current_tenant.get() != schema_name:
            raise BusinessRuleViolationError(invalid)
        if not settings.TESTING and connection.schema_name != schema_name:
            raise BusinessRuleViolationError(invalid)
        if schema_name != "public":
            try:
                SchoolSelector().get_active_by_schema(schema_name)
            except ObjectNotFoundError:
                raise BusinessRuleViolationError(invalid) from None
        try:
            user = CustomUser.objects.select_for_update().get(pk=user_id, is_active=True)
        except (CustomUser.DoesNotExist, ValueError):
            raise BusinessRuleViolationError(invalid) from None
        if (
            not user.has_usable_password()
            or not recovery_token_generator.check_token(user, token)
            or (schema_name == "public" and not (user.is_staff or user.is_superuser))
        ):
            raise BusinessRuleViolationError(invalid)
        AccountService._validate_password(password, user=user)
        self.user = user
        old = self._snapshot(user, ["password"])
        user.set_password(password)
        user.updated_by = user
        user.save(update_fields=["password", "updated_by", "updated_at"])
        self._record_audit("UPDATE", user, old_values=old)
        self._log("account_password_recovered", user_id=str(user.pk))
        return user
