"""Jornada HTTP de criação e ativação da equipe administrativa."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.forms import TeacherInvitationForm
from accounts.staff_forms import StaffUserForm
from accounts.staff_services import StaffAccountService
from base.exceptions import BusinessRuleViolationError, ValidationError
from base.forms import apply_validation_errors


@login_required
def staff_user_create(request):
    """Cadastra colaborador e entrega convite após commit."""
    form = StaffUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = StaffAccountService(user=request.user).create_staff_user(form.cleaned_data)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(
                request, "Conta criada. O convite de ativação foi agendado para envio."
            )
            return redirect("user_detail", pk=user.pk)
    return render(
        request, "accounts/staff_user_form.html", {"form": form, "title": "Convidar colaborador"}
    )


@login_required
@require_POST
def staff_user_invite(request, pk):
    """Reenvia o convite e invalida a emissão anterior."""
    try:
        StaffAccountService(user=request.user).send_staff_invitation(pk)
    except (ValidationError, BusinessRuleViolationError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Novo convite agendado. O link anterior deixou de funcionar.")
    return redirect("user_detail", pk=pk)


def staff_invitation(request):
    """Permite à pessoa convidada definir sua própria senha."""
    token = request.GET.get("token") or request.POST.get("token", "")
    form = TeacherInvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            StaffAccountService().activate_staff_invitation(token, form.cleaned_data["password"])
        except ValidationError as exc:
            for errors in exc.errors.values():
                for error in errors:
                    form.add_error("password", error)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(request, "Acesso ativado. Entre com seu e-mail e sua senha.")
            return redirect("login")
    return render(request, "auth/staff_invitation.html", {"form": form, "token": token})
