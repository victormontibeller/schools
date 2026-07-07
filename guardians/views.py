"""Views do módulo de responsáveis."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ValidationError
from base.listing import build_querystring, build_sorting, resolve_listing_state
from guardians.forms import GuardianEditForm, GuardianForm
from guardians.selectors import GuardianSelector
from guardians.services import GuardianService

GUARDIAN_SORTS = {
    "name": "user__first_name",
    "-name": "-user__first_name",
    "relationship_type": "relationship_type",
    "-relationship_type": "-relationship_type",
    "cpf": "cpf",
    "-cpf": "-cpf",
}


@login_required
def guardians_list(request):
    """Lista responsáveis paginados, com busca por nome e suporte a HTMX."""
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="guardians_list",
        allowed_sorts=set(GUARDIAN_SORTS),
        default_sort="name",
    )
    search = state["q"]
    sort = state["sort"]
    result = GuardianSelector().list_guardians(
        search=search,
        order_by=GUARDIAN_SORTS[sort],
        page=page,
    )
    ctx = {
        "result": result,
        "q": search,
        "sort": sort,
        "sorting": build_sorting(
            current_sort=sort,
            search=search,
            sortable_fields=["name", "relationship_type", "cpf"],
        ),
        "list_query": build_querystring({"q": search, "sort": sort}),
        "clear_query": build_querystring({"q": "", "sort": "name"}, include_blank=True),
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
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "guardians/partials/guardian_information_card.html",
            {"guardian": guardian},
        )
    return render(
        request,
        "guardians/guardian_detail.html",
        {"guardian": guardian, "students": students, "addresses": addresses},
    )


@login_required
def guardian_edit(request, pk):
    """Edita as informações do responsável dentro do card de perfil."""
    guardian = GuardianSelector().get_by_id(pk)

    if request.method == "POST":
        form = GuardianEditForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                data = _submitted_form_data(form.cleaned_data, request)
                guardian = GuardianService(user=request.user).update_guardian(pk, data)
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "guardians/partials/guardian_information_card.html",
                        {"guardian": guardian, "saved": True},
                    )
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
                "first_name": guardian.user.first_name,
                "last_name": guardian.user.last_name,
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

    if not request.headers.get("HX-Request"):
        return redirect("guardian_detail", pk=pk)
    return render(
        request,
        "guardians/partials/guardian_information_form.html",
        {"form": form, "guardian": guardian},
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


def _submitted_form_data(cleaned_data: dict, request) -> dict:
    """Retorna apenas campos enviados para preservar updates parciais."""
    submitted = set(request.POST) | set(request.FILES)
    return {key: value for key, value in cleaned_data.items() if key in submitted}
