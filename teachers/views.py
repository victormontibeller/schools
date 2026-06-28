from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from teachers.selectors import TeacherSelector


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
    subjects = teacher.subjects.all()
    return render(
        request, "teachers/teacher_detail.html", {"teacher": teacher, "subjects": subjects}
    )
