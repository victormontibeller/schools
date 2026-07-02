"""Views do módulo de professores."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ValidationError
from teachers.forms import SubjectForm, TeacherEditForm, TeacherForm, TeacherSubjectsForm
from teachers.selectors import SubjectSelector, TeacherSelector
from teachers.services import SubjectService, TeacherService


@login_required
def teachers_list(request):
    """Lista professores paginados, com busca por nome e suporte a HTMX."""
    page = int(request.GET.get("page", 1))
    search = request.GET.get("q", "").strip()
    filters = {}
    if search:
        filters["user__first_name__icontains"] = search
    result = TeacherSelector().list_teachers(filters=filters, page=page)
    ctx = {
        "result": result,
        "q": search,
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Professores", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "teachers/partials/teachers_table.html", ctx)
    return render(request, "teachers/teachers_list.html", ctx)


@login_required
def teacher_detail(request, pk):
    """Exibe o detalhe do professor e as disciplinas atribuídas."""
    from addresses.selectors import AddressSelector

    teacher = TeacherSelector().get_by_id(pk)
    subjects = TeacherSelector().list_teacher_subjects(teacher.pk)
    addresses = AddressSelector().get_by_entity("teacher", teacher.pk)
    if request.headers.get("HX-Request"):
        component = request.GET.get("component")
        if component == "information":
            return render(
                request,
                "teachers/partials/teacher_information_card.html",
                {"teacher": teacher},
            )
        if component == "subjects":
            return render(
                request,
                "teachers/partials/teacher_subjects_card.html",
                {"teacher": teacher, "subjects": subjects},
            )
    return render(
        request,
        "teachers/teacher_detail.html",
        {"teacher": teacher, "subjects": subjects, "addresses": addresses},
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


@login_required
def teacher_edit(request, pk):
    """Edita os dados do professor dentro do card de informações."""
    teacher = TeacherSelector().get_by_id(pk)
    if request.GET.get("component") == "subjects":
        return _teacher_subjects_response(request, teacher)

    if request.method == "POST":
        form = TeacherEditForm(request.POST)
        if form.is_valid():
            try:
                teacher = TeacherService(user=request.user).update_teacher(pk, form.cleaned_data)
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "teachers/partials/teacher_information_card.html",
                        {"teacher": teacher, "saved": True},
                    )
                messages.success(request, "Professor atualizado.")
                return redirect("teacher_detail", pk=pk)
            except ValidationError as exc:
                for field, errors in exc.errors.items():
                    for error in errors:
                        form.add_error(field if field != "__all__" else None, error)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        form = TeacherEditForm(
            initial={
                "registration_number": teacher.registration_number,
                "hire_date": teacher.hire_date,
                "birth_date": teacher.birth_date,
                "gender": teacher.gender,
                "nationality": teacher.nationality,
                "cpf": teacher.cpf or "",
                "rg_number": teacher.rg_number,
                "rg_issuer": teacher.rg_issuer,
                "rg_state": teacher.rg_state,
                "phone_mobile": teacher.phone_mobile,
            }
        )

    if not request.headers.get("HX-Request"):
        return redirect("teacher_detail", pk=pk)
    return render(
        request,
        "teachers/partials/teacher_information_form.html",
        {"form": form, "teacher": teacher},
    )


@login_required
def teacher_subjects_edit(request, pk):
    """Mantém compatibilidade com a rota dedicada de disciplinas."""
    teacher = TeacherSelector().get_by_id(pk)
    return _teacher_subjects_response(request, teacher)


def _teacher_subjects_response(request, teacher):
    """Renderiza e processa o componente de vínculos de disciplinas."""
    if request.method == "POST":
        form = TeacherSubjectsForm(request.POST)
        if form.is_valid():
            teacher = TeacherService(user=request.user).set_subjects(
                teacher.pk, form.cleaned_data["subjects"]
            )
            subjects = TeacherSelector().list_teacher_subjects(teacher.pk)
            if request.headers.get("HX-Request"):
                return render(
                    request,
                    "teachers/partials/teacher_subjects_card.html",
                    {"teacher": teacher, "subjects": subjects, "saved": True},
                )
            messages.success(request, "Disciplinas do professor atualizadas.")
            return redirect("teacher_detail", pk=teacher.pk)
    else:
        form = TeacherSubjectsForm(initial={"subjects": teacher.subjects.all()})

    if not request.headers.get("HX-Request"):
        return redirect("teacher_detail", pk=teacher.pk)
    return render(
        request,
        "teachers/partials/teacher_subjects_form.html",
        {"form": form, "teacher": teacher},
    )


# ── Subjects (Disciplinas) ───────────────────────────────────────────────────


@login_required
def subjects_list(request):
    """Lista disciplinas paginadas, com busca por nome e suporte a HTMX."""
    page = int(request.GET.get("page", 1))
    search = request.GET.get("q", "").strip()
    filters = {}
    if search:
        filters["name__icontains"] = search
    result = SubjectSelector().list_subjects(filters=filters, page=page)
    ctx = {
        "result": result,
        "q": search,
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Disciplinas", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "teachers/partials/subjects_table.html", ctx)
    return render(request, "teachers/subjects_list.html", ctx)
    return render(request, "teachers/subjects_list.html", {"result": result, "q": search})


@login_required
def subject_create(request):
    """Processa o formulário de criação de disciplina."""
    form = SubjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            SubjectService(user=request.user).create_subject(form.cleaned_data)
            messages.success(request, "Disciplina criada com sucesso.")
            return redirect("subjects_list")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)
    return render(request, "teachers/subject_form.html", {"form": form, "title": "Nova Disciplina"})


@login_required
def subject_edit(request, pk):
    """Processa o formulário de edição de disciplina."""
    subject = SubjectSelector().get_by_id(pk)
    form = SubjectForm(request.POST or None, instance=subject)
    if request.method == "POST" and form.is_valid():
        try:
            SubjectService(user=request.user).update_subject(pk, form.cleaned_data)
            messages.success(request, "Disciplina atualizada.")
            return redirect("subjects_list")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)
    return render(
        request,
        "teachers/subject_form.html",
        {"form": form, "title": "Editar Disciplina", "instance": subject},
    )


@login_required
def subject_deactivate(request, pk):
    """Desativa uma disciplina via HTMX."""
    if request.method == "POST":
        try:
            SubjectService(user=request.user).deactivate_subject(pk)
            messages.success(request, "Disciplina desativada.")
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)
    return redirect("subjects_list")
