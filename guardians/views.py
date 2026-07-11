"""Views do módulo de responsáveis."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def guardians_list(request):
    """Mantém URL histórica sem oferecer gestão isolada de responsáveis."""
    return redirect("students_list")


@login_required
def guardian_detail(request, pk):
    """Redireciona ficha legada à lista de alunos."""
    return redirect("students_list")


@login_required
def guardian_edit(request, pk):
    return redirect("students_list")


@login_required
def guardian_create(request):
    return redirect("students_list")


def _submitted_form_data(cleaned_data: dict, request) -> dict:
    """Retorna apenas campos enviados para preservar updates parciais."""
    submitted = set(request.POST) | set(request.FILES)
    return {key: value for key, value in cleaned_data.items() if key in submitted}
