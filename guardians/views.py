"""Views do módulo de responsáveis."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from base.exceptions import ValidationError
from guardians.forms import GuardianForm
from guardians.models import Guardian
from guardians.selectors import GuardianSelector
from guardians.services import GuardianService


@login_required
def guardians_list(request):
    """Lista responsáveis paginados, com busca por nome e suporte a HTMX."""
    page = int(request.GET.get("page", 1))
    search = request.GET.get("q", "").strip()
    filters = {}
    if search:
        filters["user__first_name__icontains"] = search
    result = GuardianSelector().list_guardians(filters=filters, page=page)
    if request.headers.get("HX-Request"):
        return render(
            request, "guardians/partials/guardians_table.html", {"result": result, "q": search}
        )
    return render(request, "guardians/guardians_list.html", {"result": result, "q": search})


@login_required
def guardian_detail(request, pk):
    """Exibe o detalhe do responsável e os alunos vinculados."""
    guardian = get_object_or_404(Guardian, pk=pk)
    students = GuardianSelector().get_guardian_students(guardian.pk)
    return render(
        request, "guardians/guardian_detail.html", {"guardian": guardian, "students": students}
    )


@login_required
def guardian_create(request):
    """Processa o formulário de criação de responsável e redireciona em sucesso."""
    form = GuardianForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            data["user_id"] = str(data["user_id"])
            GuardianService(user=request.user).create_guardian(data)
            return redirect("guardians_list")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    return render(
        request, "guardians/guardian_form.html", {"form": form, "title": "Novo Responsável"}
    )
