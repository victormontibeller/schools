"""Views do módulo de responsáveis."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ValidationError
from guardians.forms import GuardianEditForm, GuardianForm
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
    ctx = {
        "result": result,
        "q": search,
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Responsáveis", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "guardians/partials/guardians_table.html", ctx)
    return render(request, "guardians/guardians_list.html", ctx)


@login_required
def guardian_detail(request, pk):
    """Exibe o detalhe do responsável e os alunos vinculados."""
    from addresses.selectors import AddressSelector

    guardian = GuardianSelector().get_by_id(pk)
    students = GuardianSelector().get_guardian_students(guardian.pk)
    addresses = AddressSelector().get_by_entity("guardian", guardian.pk)
    return render(
        request,
        "guardians/guardian_detail.html",
        {"guardian": guardian, "students": students, "addresses": addresses},
    )


@login_required
def guardian_edit(request, pk):
    """Processa o formulário de edição de responsável."""
    guardian = GuardianSelector().get_by_id(pk)

    if request.method == "POST":
        form = GuardianEditForm(request.POST)
        if form.is_valid():
            try:
                GuardianService(user=request.user).update_guardian(pk, form.cleaned_data)
                messages.success(request, "Responsável atualizado.")
                return redirect("guardian_detail", pk=pk)
            except ValidationError as exc:
                for field, errors in exc.errors.items():
                    for error in errors:
                        form.add_error(field if field != "__all__" else None, error)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        form = GuardianEditForm(
            initial={
                "relationship_type": guardian.relationship_type,
                "birth_date": guardian.birth_date,
                "gender": guardian.gender,
                "nationality": guardian.nationality,
                "cpf": guardian.cpf or "",
                "rg_number": guardian.rg_number,
                "rg_issuer": guardian.rg_issuer,
                "rg_state": guardian.rg_state,
                "phone": guardian.phone,
                "phone_whatsapp": guardian.phone_whatsapp,
                "phone_mobile": guardian.phone_mobile,
            }
        )

    return render(
        request,
        "guardians/guardian_form.html",
        {"form": form, "title": "Editar Responsável", "instance": guardian},
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
