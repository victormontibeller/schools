"""HTTP nativo Django; confirmação delegada ao comando seguro."""

from django.contrib.auth.views import (
    INTERNAL_RESET_SESSION_TOKEN,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.http import HttpResponseRedirect

from accounts.recovery_forms import SchoolPasswordResetForm
from accounts.recovery_services import PasswordRecoveryService
from accounts.recovery_tokens import recovery_token_generator
from base.context import current_tenant
from base.exceptions import BusinessRuleViolationError, ValidationError


class SchoolPasswordResetView(PasswordResetView):
    form_class = SchoolPasswordResetForm
    token_generator = recovery_token_generator


class SchoolPasswordResetConfirmView(PasswordResetConfirmView):
    token_generator = recovery_token_generator

    def form_valid(self, form):
        try:
            PasswordRecoveryService().confirm_password_reset(
                user_id=self.user.pk,
                token=self.request.session.get(INTERNAL_RESET_SESSION_TOKEN),
                password=form.cleaned_data["new_password1"],
                schema_name=current_tenant.get(),
            )
        except ValidationError as exc:
            for errors in exc.errors.values():
                for error in errors:
                    form.add_error("new_password1", error)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
        else:
            self.request.session.pop(INTERNAL_RESET_SESSION_TOKEN, None)
            return HttpResponseRedirect(self.get_success_url())
        return self.form_invalid(form)
