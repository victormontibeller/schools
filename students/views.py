from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import ValidationError
from base.listing import build_querystring, build_sorting, resolve_listing_state
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
    result = StudentSelector().list_students(
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
            {"label": "Alunos", "url": None},
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
                messages.error(request, exc.message)
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


def _submitted_form_data(cleaned_data: dict, request) -> dict:
    """Retorna apenas campos enviados para preservar updates parciais."""
    submitted = set(request.POST) | set(request.FILES)
    return {key: value for key, value in cleaned_data.items() if key in submitted}
