"""Views de responsáveis e vínculos com alunos."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.listing import build_querystring, resolve_listing_state
from base.media import private_file_response
from guardians.forms import GuardianEditForm, GuardianLinkForm
from guardians.selectors import GuardianSelector
from guardians.services import GuardianService


@login_required
def guardian_avatar(request, pk):
    """Entrega a foto privada do responsável dentro do escopo autorizado."""
    guardian = GuardianSelector().get_by_id(pk)
    from core.permissions import can_access_module

    allowed = guardian.user_id == request.user.pk or can_access_module(request.user, "guardians")
    if not allowed:
        raise PermissionDeniedError("Sem permissão para acessar esta foto.")
    if not guardian.avatar:
        raise ObjectNotFoundError("GuardianAvatar", str(pk))
    return private_file_response(guardian.avatar, as_attachment=False)


@login_required
def guardians_list(request):
    """Lista responsáveis com busca e paginação."""
    state = resolve_listing_state(
        request, scope="guardians_list", allowed_sorts={"name", "-name"}, default_sort="name"
    )
    order = "-first_name" if state["sort"] == "-name" else "first_name"
    result = GuardianSelector().list_guardians(
        search=state["q"], order_by=order, page=int(request.GET.get("page", 1))
    )
    context = {
        "result": result,
        "q": state["q"],
        "sort": state["sort"],
        "list_query": build_querystring({"q": state["q"], "sort": state["sort"]}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Responsáveis", "url": None},
        ],
    }
    template = (
        "guardians/partials/guardians_table.html"
        if request.headers.get("HX-Request")
        else "guardians/guardians_list.html"
    )
    return render(request, template, context)


@login_required
def guardian_detail(request, pk):
    """Exibe dados e alunos vinculados ao responsável."""
    from addresses.selectors import AddressSelector

    guardian = GuardianSelector().get_by_id(pk)
    return render(
        request,
        "guardians/guardian_detail.html",
        {
            "guardian": guardian,
            "students": GuardianSelector().get_guardian_students(pk),
            "addresses": AddressSelector().get_by_entity("guardian", pk),
        },
    )


@login_required
def guardian_create(request):
    """Cria um responsável independente de vínculo inicial."""
    form = GuardianEditForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            guardian = GuardianService(user=request.user).create_guardian(form.cleaned_data)
            messages.success(request, "Responsável criado com sucesso.")
            return redirect("guardian_edit", pk=guardian.pk)
        except ValidationError as exc:
            _add_service_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
    return render(
        request,
        "guardians/guardian_form.html",
        {"form": form, "title": "Novo Responsável", "guardian": None, "students": []},
    )


@login_required
def guardian_edit(request, pk):
    """Edita o responsável e mantém os vínculos na mesma tela."""
    guardian = GuardianSelector().get_by_id(pk)
    initial = {
        name: getattr(guardian, name)
        for name in GuardianEditForm.base_fields
        if name != "avatar" and hasattr(guardian, name)
    }
    form = GuardianEditForm(
        request.POST or None,
        request.FILES or None,
        initial=initial,
        require_version=True,
    )
    if request.method == "POST" and form.is_valid():
        try:
            guardian = GuardianService(user=request.user).update_guardian(pk, form.cleaned_data)
            messages.success(request, "Responsável atualizado.")
            return redirect("guardian_edit", pk=guardian.pk)
        except (ValidationError, BusinessRuleViolationError) as exc:
            _add_service_errors(form, exc)
    return render(
        request,
        "guardians/guardian_form.html",
        {
            "form": form,
            "title": "Editar Responsável",
            "guardian": guardian,
            "students": GuardianSelector().get_guardian_students(pk),
            "link_form": GuardianLinkForm(),
        },
    )


@login_required
def guardian_student_search(request, pk):
    """Pesquisa alunos ainda não vinculados ao responsável."""
    from students.selectors import StudentSelector

    students = StudentSelector().search_for_guardian(request.GET.get("q", ""), guardian_id=pk)
    return render(
        request,
        "guardians/partials/student_search_results.html",
        {"guardian": GuardianSelector().get_by_id(pk), "students": students},
    )


@login_required
def guardian_student_link(request, pk, student_id):
    """Cria vínculo a partir da tela de edição do responsável."""
    if request.method == "POST":
        form = GuardianLinkForm(request.POST)
        if form.is_valid():
            GuardianService(user=request.user).link_student(pk, student_id, form.cleaned_data)
            messages.success(request, "Aluno vinculado ao responsável.")
    return redirect("guardian_edit", pk=pk)


@login_required
def guardian_student_unlink(request, pk, student_id):
    """Desativa o vínculo entre responsável e aluno."""
    if request.method == "POST":
        GuardianService(user=request.user).unlink_student(pk, student_id)
        messages.success(request, "Vínculo removido.")
    return redirect("guardian_edit", pk=pk)


def _add_service_errors(form, exc) -> None:
    """Converte erros de domínio em erros do formulário."""
    if isinstance(exc, ValidationError):
        for field, errors in exc.errors.items():
            for error in errors:
                form.add_error(field if field in form.fields else None, error)
    else:
        form.add_error(None, exc.message)
