"""Views de configuração dos aspectos e opções da Agenda."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_querystring, build_sorting, resolve_listing_state
from core.access_catalog import CREATE, EDIT, VIEW
from core.permissions import access_policy
from student_diary.forms import (
    RoutineAspectForm,
    RoutineAspectToggleForm,
    RoutineOptionForm,
    RoutineOptionToggleForm,
)
from student_diary.selectors import StudentDiarySelector
from student_diary.services import StudentDiaryService


@login_required
@access_policy("diary_configuration", VIEW)
def diary_configuration(request):
    """Lista o catálogo configurável de aspectos da rotina."""
    state = resolve_listing_state(
        request,
        scope="diary_configuration",
        allowed_sorts={
            "name",
            "-name",
            "display_order",
            "-display_order",
            "is_enabled",
            "-is_enabled",
        },
        default_sort="display_order",
    )
    result = StudentDiarySelector().list_categories_page(
        search=state["q"],
        order_by=state["sort"],
        page=int(request.GET.get("page", 1)),
    )
    context = {
        "result": result,
        "q": state["q"],
        "sort": state["sort"],
        "sorting": build_sorting(
            current_sort=state["sort"],
            search=state["q"],
            sortable_fields=["name", "display_order", "is_enabled"],
        ),
        "list_query": build_querystring({"q": state["q"], "sort": state["sort"]}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Aspectos da rotina", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "student_diary/partials/categories_table.html", context)
    return render(request, "student_diary/configuration.html", context)


@login_required
@access_policy("diary_configuration", CREATE)
def diary_aspect_create(request):
    """Cria um aspecto inativo e encaminha para o cadastro de opções."""
    form = RoutineAspectForm(
        request.POST or None,
        initial={
            "is_required": True,
            "display_order": StudentDiarySelector().next_category_display_order(),
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            category = StudentDiaryService(user=request.user).create_routine_aspect(
                form.cleaned_data
            )
            messages.success(request, "Aspecto criado. Cadastre as opções antes de ativá-lo.")
            return redirect("diary_aspect_detail", category_id=category.pk)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
    return render(
        request,
        "student_diary/aspect_form.html",
        {"form": form, "title": "Novo aspecto da rotina"},
    )


@login_required
@access_policy("diary_configuration", VIEW)
def diary_aspect_detail(request, category_id):
    """Exibe a ficha de um aspecto e suas opções."""
    category = StudentDiarySelector().get_category_with_options(category_id)
    if request.headers.get("HX-Request"):
        component = request.GET.get("component")
        if component == "information":
            return _render_information(request, category)
        if component == "options":
            return _render_options(request, category)
    return render(request, "student_diary/category_detail.html", {"category": category})


@login_required
@access_policy("diary_configuration", EDIT)
def diary_aspect_edit(request, category_id):
    """Edita o aspecto substituindo somente seu card de informações."""
    category = StudentDiarySelector().get_category_with_options(category_id)
    form = RoutineAspectForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        try:
            category = StudentDiaryService(user=request.user).update_routine_aspect(
                category_id, form.cleaned_data
            )
            return _render_information(request, category, saved=True)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
    if not request.headers.get("HX-Request"):
        return redirect("diary_aspect_detail", category_id=category_id)
    return _render_information_form(request, category, form, "Editar aspecto", request.path)


@login_required
@access_policy("diary_configuration", EDIT)
def diary_aspect_toggle(request, category_id):
    """Mantém a rota compatível de ativação reversível do aspecto."""
    category = StudentDiarySelector().get_category_with_options(category_id)
    form = RoutineAspectToggleForm(
        request.POST if request.method == "POST" else None,
        instance=category,
    )
    if request.method == "POST" and form.is_valid():
        try:
            category = StudentDiaryService(user=request.user).set_routine_aspect_enabled(
                category_id,
                form.cleaned_data["is_enabled"],
                form.cleaned_data["version"],
            )
            if request.headers.get("HX-Request"):
                return _render_information(request, category, saved=True)
            messages.success(request, "Aspecto da rotina atualizado.")
            return redirect("diary_aspect_detail", category_id=category_id)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
    if not request.headers.get("HX-Request"):
        return redirect("diary_aspect_detail", category_id=category_id)
    return _render_information_form(
        request, category, form, "Disponibilidade do aspecto", request.path
    )


@login_required
@access_policy("diary_configuration", CREATE)
def diary_option_create(request, category_id):
    """Adiciona uma opção no card do aspecto."""
    category = StudentDiarySelector().get_category_with_options(category_id)
    initial_order = max((option.display_order for option in category.options.all()), default=0) + 1
    form = RoutineOptionForm(request.POST or None, initial={"display_order": initial_order})
    if request.method == "POST" and form.is_valid():
        try:
            StudentDiaryService(user=request.user).create_routine_option(
                category_id, form.cleaned_data
            )
            category = StudentDiarySelector().get_category_with_options(category_id)
            return _render_options(request, category, saved=True)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
    if not request.headers.get("HX-Request"):
        return redirect("diary_aspect_detail", category_id=category_id)
    return _render_option_form(request, category, form, "Nova opção", request.path)


@login_required
@access_policy("diary_configuration", EDIT)
def diary_option_edit(request, category_id, option_id):
    """Edita uma opção dentro do card do catálogo."""
    category = StudentDiarySelector().get_category_with_options(category_id)
    option = _option_from_category(category, option_id)
    form = RoutineOptionForm(request.POST or None, instance=option)
    if request.method == "POST" and form.is_valid():
        try:
            StudentDiaryService(user=request.user).update_routine_option(
                category_id, option_id, form.cleaned_data
            )
            category = StudentDiarySelector().get_category_with_options(category_id)
            return _render_options(request, category, saved=True)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
    if not request.headers.get("HX-Request"):
        return redirect("diary_aspect_detail", category_id=category_id)
    return _render_option_form(request, category, form, "Editar opção", request.path)


@login_required
@access_policy("diary_configuration", EDIT)
def diary_option_toggle(request, category_id, option_id):
    """Ativa ou desativa uma opção e redesenha somente o card."""
    category = StudentDiarySelector().get_category_with_options(category_id)
    option = _option_from_category(category, option_id)
    form = RoutineOptionToggleForm(request.POST or None, instance=option)
    if request.method == "POST" and form.is_valid():
        try:
            StudentDiaryService(user=request.user).set_routine_option_enabled(
                category_id,
                option_id,
                form.cleaned_data["is_enabled"],
                form.cleaned_data["version"],
            )
            category = StudentDiarySelector().get_category_with_options(category_id)
            return _render_options(request, category, saved=True)
        except BusinessRuleViolationError as exc:
            category = StudentDiarySelector().get_category_with_options(category_id)
            return _render_options(request, category, component_error=exc.message)
    if not request.headers.get("HX-Request"):
        return redirect("diary_aspect_detail", category_id=category_id)
    return _render_option_form(request, category, form, "Disponibilidade da opção", request.path)


def _option_from_category(category, option_id):
    """Resolve uma opção já carregada sem consultar o ORM na view."""
    option = next((item for item in category.options.all() if str(item.pk) == str(option_id)), None)
    if option is None:
        raise ObjectNotFoundError("DiaryOption", str(option_id))
    return option


def _render_information(request, category, *, saved=False):
    return render(
        request,
        "student_diary/partials/category_information_card.html",
        {"category": category, "saved": saved},
    )


def _render_options(request, category, *, saved=False, component_error=None):
    return render(
        request,
        "student_diary/partials/category_options_card.html",
        {
            "category": category,
            "saved": saved,
            "component_error": component_error,
        },
    )


def _render_information_form(request, category, form, title, edit_url):
    return render(
        request,
        "partials/information_form_card.html",
        {
            "form": form,
            "component_id": "diary-category-information-card",
            "component_title": title,
            "edit_url": edit_url,
            "cancel_url": (
                f"{reverse('diary_aspect_detail', args=[category.pk])}" "?component=information"
            ),
        },
    )


def _render_option_form(request, category, form, title, edit_url):
    return render(
        request,
        "student_diary/partials/category_option_form_card.html",
        {
            "category": category,
            "form": form,
            "component_title": title,
            "edit_url": edit_url,
        },
    )
