"""Orquestração HTTP da central de configuração de acessos."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from core.permissions import EDIT, access_policy


@login_required
@access_policy("__admin__", EDIT)
def access_settings(request: HttpRequest) -> HttpResponse:
    """Exibe e atualiza a matriz completa de grupos do tenant."""
    from base.exceptions import BusinessRuleViolationError, ValidationError
    from core.access.forms import AccessConfigurationForm
    from core.access.selectors import AccessConfigurationSelector
    from core.access.services import AccessConfigurationService

    is_matrix_request = request.headers.get("HX-Target") == "access-matrix-card"
    saved = False

    if request.method == "POST":
        form = AccessConfigurationForm(request.POST)
        if form.is_valid():
            try:
                AccessConfigurationService(user=request.user).update_access_matrix(
                    form.cleaned_data["access_matrix"],
                    form.cleaned_data["expected_versions"],
                )
                if not is_matrix_request:
                    messages.success(request, "Acessos atualizados com sucesso.")
                    return redirect(reverse("access_settings"))
                saved = True
                selector = AccessConfigurationSelector()
                matrix = selector.get_full_matrix()
                versions = {role.name: role.version for role in matrix.roles}
                form = AccessConfigurationForm(
                    initial_access=matrix.values,
                    versions=versions,
                )
            except (BusinessRuleViolationError, ValidationError) as exc:
                form.add_error(None, exc.message)
    else:
        selector = AccessConfigurationSelector()
        matrix = selector.get_full_matrix()
        versions = {role.name: role.version for role in matrix.roles}
        form = AccessConfigurationForm(
            initial_access=matrix.values,
            versions=versions,
        )

    context = {"form": form, "saved": saved}
    if is_matrix_request:
        return render(request, "core/access/partials/access_matrix_card.html", context)
    return render(request, "core/access/access_settings.html", context)
