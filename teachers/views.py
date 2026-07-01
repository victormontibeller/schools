"""Views do módulo de professores."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from base.exceptions import ValidationError
from teachers.forms import TeacherForm
from teachers.selectors import TeacherSelector
from teachers.services import TeacherService


@login_required
def teachers_list(request):
    """Lista professores paginados, com busca por nome e suporte a HTMX."""
    page = int(request.GET.get("page", 1))
    search = request.GET.get("q", "").strip()
    filters = {}
    if search:
        filters["user__first_name__icontains"] = search
    result = TeacherSelector().list_teachers(filters=filters, page=page)
    if request.headers.get("HX-Request"):
        return render(
            request, "teachers/partials/teachers_table.html", {"result": result, "q": search}
        )
    return render(request, "teachers/teachers_list.html", {"result": result, "q": search})


@login_required
def teacher_detail(request, pk):
    """Exibe o detalhe do professor e as disciplinas atribuídas."""
    from teachers.models import Teacher

    teacher = get_object_or_404(Teacher, pk=pk)
    subjects = TeacherSelector().list_teacher_subjects(teacher.pk)
    return render(
        request, "teachers/teacher_detail.html", {"teacher": teacher, "subjects": subjects}
    )


@login_required
def teacher_create(request):
    """Processa o formulário de criação de professor e redireciona em sucesso."""
    form = TeacherForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            data["user_id"] = str(data["user_id"])
            TeacherService(user=request.user).create_teacher(data)
            return redirect("teachers_list")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    return render(request, "teachers/teacher_form.html", {"form": form, "title": "Novo Professor"})
