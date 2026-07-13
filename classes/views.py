"""Views HTMX para turmas e matriculas."""

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.listing import build_querystring, build_sorting, resolve_listing_state
from classes.forms import ClassForm
from classes.selectors import ClassSelector
from classes.services import ClassService

logger = logging.getLogger(__name__)


@login_required
def classes_list(request):
    """Lista turmas paginadas; suporta busca por nome."""
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="classes_list",
        allowed_sorts={
            "name",
            "-name",
            "grade",
            "-grade",
            "education_stage",
            "-education_stage",
            "shift",
            "-shift",
            "academic_year",
            "-academic_year",
            "max_students",
            "-max_students",
        },
        default_sort="-academic_year",
    )
    search, sort = state["q"], state["sort"]
    filters = {}
    if search:
        filters["name__icontains"] = search

    result = ClassSelector().list_classes(filters=filters, order_by=sort, page=page)

    ctx = {
        "result": result,
        "q": search,
        "sort": sort,
        "sorting": build_sorting(
            current_sort=sort,
            search=search,
            sortable_fields=[
                "name",
                "grade",
                "education_stage",
                "shift",
                "academic_year",
                "max_students",
            ],
        ),
        "list_query": build_querystring({"q": search, "sort": sort}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Turmas", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "classes/partials/classes_table.html", ctx)
    return render(request, "classes/classes_list.html", ctx)


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
    cls = ClassSelector().get_by_id(pk)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "classes/partials/class_information_card.html",
            {"class_obj": cls},
        )
    enrollments = ClassSelector().get_class_students(cls.pk)
    return render(
        request,
        "classes/class_detail.html",
        {"class_obj": cls, "enrollments": enrollments},
    )


@login_required
def class_edit(request, pk):
    """Edita a turma substituindo apenas o card de informações."""
    cls = ClassSelector().get_by_id(pk)
    form = ClassForm(request.POST or None, instance=cls)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            teacher = data.pop("class_teacher", None)
            data["class_teacher_id"] = teacher.pk if teacher else None
            cls = ClassService(user=request.user).update_class(pk, data)
            if request.headers.get("HX-Request"):
                return render(
                    request,
                    "classes/partials/class_information_card.html",
                    {"class_obj": cls, "saved": True},
                )
            return redirect("class_detail", pk=pk)
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    if not request.headers.get("HX-Request"):
        return redirect("class_detail", pk=pk)
    return render(
        request,
        "classes/partials/class_information_form_card.html",
        {
            "form": form,
            "edit_url": request.path,
            "cancel_url": f"{request.path_info.removesuffix('editar/')}?component=information",
        },
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
    except (ValidationError, ObjectNotFoundError, BusinessRuleViolationError) as exc:
        logger.warning("Erro ao matricular aluno: %s", exc, extra={"class_id": str(class_id)})
        from django.contrib import messages

        messages.error(request, str(exc))

    return redirect("class_detail", pk=class_id)


@login_required
def class_student_search(request, class_id):
    """Retorna resultados HTMX para matrícula na turma."""
    cls = ClassSelector().get_by_id(class_id)
    students = ClassSelector().search_enrollable_students(class_id, request.GET.get("q", ""))
    return render(
        request,
        "classes/partials/student_search_results.html",
        {"class_obj": cls, "students": students},
    )
