"""Views HTMX para turmas e matrículas."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from base.exceptions import ValidationError
from classes.forms import ClassForm
from classes.selectors import ClassSelector
from classes.services import ClassService


@login_required
def classes_list(request):
    """Lista turmas paginadas; suporta busca por nome."""
    page = int(request.GET.get("page", 1))
    search = request.GET.get("q", "").strip()
    filters = {}
    if search:
        filters["name__icontains"] = search

    result = ClassSelector().list_classes(filters=filters, page=page)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "classes/partials/classes_table.html",
            {"result": result, "q": search},
        )
    return render(
        request,
        "classes/classes_list.html",
        {"result": result, "q": search},
    )


@login_required
def class_create(request):
    """Exibe/Processa o formulário de criação de turma."""
    form = ClassForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            ClassService(user=request.user).create_class(form.cleaned_data)
            return redirect("classes_list")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    return render(
        request,
        "classes/class_form.html",
        {"form": form, "title": "Nova Turma"},
    )


@login_required
def class_detail(request, pk):
    """Exibe detalhes da turma e lista alunos matriculados."""
    from classes.models import Class

    cls = get_object_or_404(Class, pk=pk)
    enrollments = ClassSelector().get_class_students(cls.pk)
    return render(
        request,
        "classes/class_detail.html",
        {"class_obj": cls, "enrollments": enrollments},
    )


@login_required
def class_enroll(request, class_id):
    """Matrícula um aluno na turma via HTMX/post."""
    if request.method != "POST":
        return redirect("class_detail", pk=class_id)

    student_id = request.POST.get("student_id", "").strip()
    if not student_id:
        return redirect("class_detail", pk=class_id)

    try:
        ClassService(user=request.user).enroll_student(class_id, student_id)
    except Exception as exc:
        from django.contrib import messages

        messages.error(request, str(exc))

    return redirect("class_detail", pk=class_id)
