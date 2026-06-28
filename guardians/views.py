from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from guardians.models import Guardian
from guardians.selectors import GuardianSelector


@login_required
def guardians_list(request):
    """Lista responsáveis paginados, com busca por nome e suporte a HTMX."""
    page = int(request.GET.get("page", 1))
    search = request.GET.get("q", "").strip()
    filters = {}
    if search:
        filters["user__first_name__icontains"] = search
    result = GuardianSelector().list_guardians(filters=filters, page=page)
    if request.headers.get("HX-Request"):
        return render(
            request, "guardians/partials/guardians_table.html", {"result": result, "q": search}
        )
    return render(request, "guardians/guardians_list.html", {"result": result, "q": search})


@login_required
def guardian_detail(request, pk):
    """Exibe o detalhe do responsável e os alunos vinculados."""
    guardian = get_object_or_404(Guardian, pk=pk)
    students = guardian.students.select_related("student").all()
    return render(
        request, "guardians/guardian_detail.html", {"guardian": guardian, "students": students}
    )
