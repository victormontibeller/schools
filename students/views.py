from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.listing import build_querystring, build_sorting, resolve_listing_state
from base.media import private_file_response
from students.forms import StudentEditForm, StudentForm
from students.selectors import StudentSelector
from students.services import StudentService

STUDENT_SORTS = {
    "name": "first_name",
    "-name": "-first_name",
    "enrollment_number": "enrollment_number",
    "-enrollment_number": "-enrollment_number",
    "birth_date": "birth_date",
    "-birth_date": "-birth_date",
}


@login_required
def student_photo(request, pk):
    """Entrega foto privada após validar papel e vínculo com o aluno."""
    student = StudentSelector().get_student_by_id(pk)
    from core.access_selectors import ObjectAccessSelector
    from core.permissions import can_access_module, role_name

    role = role_name(request.user)
    allowed = can_access_module(request.user, "students")
    if role == "GUARDIAN":
        allowed = ObjectAccessSelector.guardian_can_access_student(request.user.pk, pk)
    elif role == "TEACHER":
        allowed = ObjectAccessSelector.teacher_can_access_student(request.user.pk, pk)
    if not allowed:
        raise PermissionDeniedError("Sem permissão para acessar esta foto.")
    if not student.photo:
        raise ObjectNotFoundError("StudentPhoto", str(pk))
    return private_file_response(student.photo, as_attachment=False)


@login_required
def students_list(request):
    """Lista alunos paginados, com busca por nome e suporte a HTMX."""
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="students_list",
        allowed_sorts=set(STUDENT_SORTS),
        default_sort="name",
    )
    search = state["q"]
    sort = state["sort"]
    role_name = getattr(getattr(request.user, "role", None), "name", "")
    result = StudentSelector().list_students_for_user(
        user_id=request.user.pk,
        role_name=role_name,
        search=search,
        order_by=STUDENT_SORTS[sort],
        page=page,
    )
    ctx = {
        "result": result,
        "q": search,
        "sort": sort,
        "sorting": build_sorting(
            current_sort=sort,
            search=search,
            sortable_fields=["name", "enrollment_number", "birth_date"],
        ),
        "list_query": build_querystring({"q": search, "sort": sort}),
        "clear_query": build_querystring({"q": "", "sort": "name"}, include_blank=True),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Alunos e Responsáveis", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "students/partials/students_table.html", ctx)
    return render(request, "students/students_list.html", ctx)


@login_required
def student_create(request):
    """Processa o formulário de criação de aluno e redireciona em sucesso."""
    form = StudentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            StudentService(user=request.user).create_student(form.cleaned_data)
            return redirect("students_list")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    return render(request, "students/student_form.html", {"form": form, "title": "Novo Aluno"})


@login_required
def student_edit(request, pk):
    """Edita as informações do aluno dentro do card de perfil."""
    from django.contrib import messages

    from base.exceptions import BusinessRuleViolationError

    student = StudentSelector().get_by_id(pk)

    if request.method == "POST":
        form = StudentEditForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            try:
                data = _submitted_form_data(form.cleaned_data, request)
                student = StudentService(user=request.user).update_student(pk, data)
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "students/partials/student_information_card.html",
                        {"student": student, "saved": True},
                    )
                messages.success(request, "Aluno atualizado.")
                return redirect("student_profile", pk=pk)
            except ValidationError as exc:
                for field, errors in exc.errors.items():
                    for error in errors:
                        form.add_error(field if field != "__all__" else None, error)
            except BusinessRuleViolationError as exc:
                form.add_error(None, exc.message)
    else:
        form = StudentEditForm(instance=student)

    if not request.headers.get("HX-Request"):
        return redirect("student_profile", pk=pk)
    return render(
        request,
        "students/partials/student_information_form.html",
        {"form": form, "student": student},
    )


@login_required
def student_profile(request, pk):
    """Exibe o perfil do aluno e os responsáveis vinculados."""
    from addresses.selectors import AddressSelector

    student = StudentSelector().get_by_id(pk)
    guardians = StudentSelector().get_student_guardians(student.pk)
    addresses = AddressSelector().get_by_entity("student", student.pk)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "students/partials/student_information_card.html",
            {"student": student},
        )
    return render(
        request,
        "students/student_profile.html",
        {"student": student, "guardians": guardians, "addresses": addresses},
    )


@login_required
def student_guardians_component(request, pk):
    """Renderiza exclusivamente o card de responsáveis do aluno."""
    student = StudentSelector().get_by_id(pk)
    return _render_guardians_card(request, student)


@login_required
def student_guardian_create(request, pk):
    """Cria um responsável e seu vínculo a partir do perfil do aluno."""
    from guardians.forms import GuardianCreateForm
    from guardians.services import GuardianService

    student = StudentSelector().get_by_id(pk)
    form = GuardianCreateForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data
            GuardianService(user=request.user).create_and_link_student(student.pk, data, data)
            return _render_guardians_card(request, student, saved=True)
        except ValidationError as exc:
            _add_service_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
    return render(
        request, "students/partials/guardian_create_form.html", {"student": student, "form": form}
    )


@login_required
def student_guardian_search(request, pk):
    """Busca contatos existentes para vincular ao aluno, sem alterar estado."""
    from guardians.selectors import GuardianSelector

    student = StudentSelector().get_by_id(pk)
    query = request.GET.get("q", "").strip()
    guardians = GuardianSelector().search_reusable(query)
    return render(
        request,
        "students/partials/guardian_search_results.html",
        {"student": student, "guardians": guardians, "query": query},
    )


@login_required
def student_guardian_link(request, pk, guardian_pk):
    """Vincula um contato existente ao aluno."""
    from guardians.forms import GuardianLinkForm
    from guardians.services import GuardianService

    student = StudentSelector().get_by_id(pk)
    form = GuardianLinkForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            GuardianService(user=request.user).link_student(
                guardian_pk, student.pk, form.cleaned_data
            )
            return _render_guardians_card(request, student, saved=True)
        except (ValidationError, BusinessRuleViolationError) as exc:
            form.add_error(
                None, getattr(exc, "message", "Não foi possível vincular o responsável.")
            )
    return render(
        request,
        "students/partials/guardian_link_form.html",
        {"student": student, "form": form, "guardian_pk": guardian_pk},
    )


@login_required
def student_guardian_link_edit(request, pk, link_pk):
    """Edita somente os dados do vínculo aluno–responsável."""
    from guardians.forms import GuardianLinkForm
    from guardians.services import GuardianService

    student = StudentSelector().get_by_id(pk)
    link = _get_student_link(student, link_pk)
    form = GuardianLinkForm(
        request.POST or None,
        initial={
            "relationship_type": link.relationship_type,
            "is_primary": link.is_primary,
            "has_custody": link.has_custody,
            "can_pickup": link.can_pickup,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            GuardianService(user=request.user).update_link(link.pk, form.cleaned_data)
            return _render_guardians_card(request, student, saved=True)
        except (ValidationError, BusinessRuleViolationError) as exc:
            form.add_error(None, getattr(exc, "message", "Não foi possível atualizar o vínculo."))
    return render(
        request,
        "students/partials/guardian_link_form.html",
        {"student": student, "form": form, "link": link},
    )


@login_required
def student_guardian_contact_edit(request, pk, link_pk):
    """Edita os dados do contato sem sair do perfil do aluno."""
    from guardians.forms import GuardianContactEditForm
    from guardians.services import GuardianService

    student = StudentSelector().get_by_id(pk)
    link = _get_student_link(student, link_pk)
    guardian = link.guardian
    form = GuardianContactEditForm(
        request.POST or None,
        request.FILES or None,
        initial={
            "first_name": guardian.first_name,
            "last_name": guardian.last_name,
            "email": guardian.email,
            "birth_date": guardian.birth_date,
            "gender": guardian.gender,
            "nationality": guardian.nationality,
            "cpf": guardian.cpf,
            "rg_number": guardian.rg_number,
            "rg_issuer": guardian.rg_issuer,
            "rg_state": guardian.rg_state,
            "phone": guardian.phone,
            "phone_whatsapp": guardian.phone_whatsapp,
            "phone_mobile": guardian.phone_mobile,
            "version": guardian.version,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            GuardianService(user=request.user).update_guardian(guardian.pk, form.cleaned_data)
            return _render_guardians_card(request, student, saved=True)
        except ValidationError as exc:
            _add_service_errors(form, exc)
    return render(
        request,
        "students/partials/guardian_contact_form.html",
        {"student": student, "link": link, "form": form},
    )


@login_required
def student_guardian_unlink(request, pk, link_pk):
    """Desvincula o responsável usando exclusão lógica."""
    from guardians.services import GuardianService

    student = StudentSelector().get_by_id(pk)
    link = _get_student_link(student, link_pk)
    if request.method == "POST":
        GuardianService(user=request.user).unlink_student(link.guardian_id, student.pk)
    return _render_guardians_card(request, student, saved=True)


def _render_guardians_card(request, student, saved=False):
    return render(
        request,
        "students/partials/student_guardians_card.html",
        {
            "student": student,
            "guardians": StudentSelector().get_student_guardians(student.pk),
            "saved": saved,
        },
    )


def _get_student_link(student, link_pk):
    for link in StudentSelector().get_student_guardians(student.pk):
        if str(link.pk) == str(link_pk):
            return link
    from base.exceptions import ObjectNotFoundError

    raise ObjectNotFoundError("StudentGuardian", str(link_pk))


def _add_service_errors(form, exc):
    for field, errors in exc.errors.items():
        for error in errors:
            form.add_error(field if field != "__all__" else None, error)


def _submitted_form_data(cleaned_data: dict, request) -> dict:
    """Retorna apenas campos enviados para preservar updates parciais."""
    submitted = set(request.POST) | set(request.FILES)
    return {key: value for key, value in cleaned_data.items() if key in submitted}
