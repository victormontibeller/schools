from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

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
    if request.headers.get("HX-Request"):
        return render(
            request, "students/partials/students_table.html", {"result": result, "q": search}
        )
    return render(request, "students/students_list.html", {"result": result, "q": search})


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
def student_profile(request, pk):
    """Exibe o perfil do aluno e os responsáveis vinculados."""
    from students.models import Student

    student = get_object_or_404(Student, pk=pk)
    guardians = StudentSelector().get_student_guardians(student.pk)
    return render(
        request, "students/student_profile.html", {"student": student, "guardians": guardians}
    )
