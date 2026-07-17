"""Views públicas para ativação de contas convidadas."""

from django.contrib import messages
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ValidationError


def guardian_invitation_view(request):
    """Permite ao responsável convidado definir senha e ativar a conta."""
    from accounts.forms import TeacherInvitationForm
    from guardians.invitation_services import GuardianInvitationService

    token = request.GET.get("token") or request.POST.get("token", "")
    form = TeacherInvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            GuardianInvitationService().activate_invitation(token, form.cleaned_data["password"])
            messages.success(request, "Conta ativada. Você já pode entrar.")
            return redirect("login")
        except ValidationError as exc:
            for errors in exc.errors.values():
                for error in errors:
                    form.add_error("password", error)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
    return render(request, "auth/guardian_invitation.html", {"form": form, "token": token})
