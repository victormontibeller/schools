from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import ValidationError
from students.forms import StudentForm
from students.selectors import StudentSelector
from students.services import StudentService


@login_required
def students_list(request):
    """Lista alunos paginados, com busca por nome e suporte a HTMX."""
    page = int(request.GET.get("page", 1))
    search = request.GET.get("q", "").strip()
    filters = {}
    if search:
        filters["first_name__icontains"] = search
    result = StudentSelector().list_students(filters=filters, page=page)
    ctx = {
        "result": result,
        "q": search,
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
    """Processa o formulário de edição de aluno."""
    from django.contrib import messages

    from base.exceptions import BusinessRuleViolationError

    student = StudentSelector().get_by_id(pk)

    if request.method == "POST":
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            try:
                StudentService(user=request.user).update_student(pk, form.cleaned_data)
                messages.success(request, "Aluno atualizado.")
                return redirect("student_profile", pk=pk)
            except ValidationError as exc:
                for field, errors in exc.errors.items():
                    for error in errors:
                        form.add_error(field if field != "__all__" else None, error)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        form = StudentForm(instance=student)

    return render(
        request,
        "students/student_form.html",
        {"form": form, "title": "Editar Aluno", "instance": student},
    )


@login_required
def student_profile(request, pk):
    """Exibe o perfil do aluno e os responsáveis vinculados."""
    from addresses.selectors import AddressSelector

    student = StudentSelector().get_by_id(pk)
    guardians = StudentSelector().get_student_guardians(student.pk)
    addresses = AddressSelector().get_by_entity("student", student.pk)
    return render(
        request,
        "students/student_profile.html",
        {"student": student, "guardians": guardians, "addresses": addresses},
    )
