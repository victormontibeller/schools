"""Views de orquestração HTTP da Agenda escolar."""

from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from base.exceptions import BusinessRuleViolationError, PermissionDeniedError, ValidationError
from base.listing import build_querystring, build_sorting, resolve_listing_state
from core.access_catalog import EDIT, VIEW
from core.permissions import access_policy, can_edit_student_diary
from student_diary.forms import (
    DiaryDailyFilterForm,
    DiaryReviewForm,
    DiaryStudentEntryForm,
    RoutineAspectToggleForm,
)
from student_diary.selectors import StudentDiarySelector
from student_diary.services import StudentDiaryService


def _selected_date(raw: str | None) -> date:
    """Converte a data do filtro ou usa a data local corrente."""
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return timezone.localdate()


def _attach_entry_forms(request, sheet, meal_types, *, bind: bool = False):
    """Associa um formulário prefixado a cada linha da folha diária."""
    bound_data = request.POST if bind and request.method == "POST" else None
    for row in sheet["rows"]:
        form = DiaryStudentEntryForm(
            bound_data,
            prefix=f"student-{row['student'].pk}",
            categories=sheet["categories"],
            meal_types=meal_types,
            initial_payload=row["initial_payload"],
        )
        row["form"] = form
    return sheet["rows"]


@login_required
def diary_daily(request):
    """Exibe e salva atomicamente o card diário de uma turma infantil."""
    selector = StudentDiarySelector()
    classes = selector.list_eligible_classes(request.user)
    class_id = (request.POST.get("class_id") or request.GET.get("class_id") or "").strip()
    diary_date = _selected_date(request.POST.get("date") or request.GET.get("date"))
    filter_form = DiaryDailyFilterForm(
        classes=classes,
        initial={"class_id": class_id or None, "date": diary_date},
    )
    sheet = None
    can_edit = can_edit_student_diary(request.user)
    saved = False
    if class_id:
        class_obj = selector.get_class(class_id)
        if not classes.filter(pk=class_obj.pk).exists():
            raise PermissionDeniedError("Turma fora do escopo do usuário.")
        meal_types = StudentDiaryService.meals_for_shift(class_obj.shift)
        sheet = selector.build_daily_sheet(class_obj.pk, diary_date, meal_types)
        rows = _attach_entry_forms(request, sheet, meal_types, bind=request.method == "POST")
        if request.method == "POST":
            if not can_edit:
                raise PermissionDeniedError("Sem permissão para preencher a Agenda.")
            validation_results = [row["form"].is_valid() for row in rows]
            forms_are_valid = all(validation_results)
            if forms_are_valid:
                entries = {str(row["student"].pk): row["form"].to_payload() for row in rows}
                try:
                    StudentDiaryService(user=request.user).save_daily_diaries(
                        class_obj.pk, diary_date, entries
                    )
                    saved = True
                    if not request.headers.get("HX-Request"):
                        messages.success(request, "Agenda salva com sucesso.")
                        return redirect(
                            f"{request.path}?class_id={class_obj.pk}&date={diary_date.isoformat()}"
                        )
                    sheet = selector.build_daily_sheet(class_obj.pk, diary_date, meal_types)
                    _attach_entry_forms(request, sheet, meal_types)
                except (ValidationError, BusinessRuleViolationError) as exc:
                    if request.headers.get("HX-Request"):
                        sheet["component_error"] = str(exc)
                    else:
                        messages.error(request, str(exc))
    context = {
        "classes": classes,
        "filter_form": filter_form,
        "class_id": class_id,
        "selected_date": diary_date,
        "sheet": sheet,
        "can_edit": can_edit
        and (
            not sheet
            or not sheet["workflow"]
            or sheet["workflow"].status in {"DRAFT", "CHANGES_REQUESTED"}
        ),
        "saved": saved,
        "can_review": _can_review(request.user),
        "publication_enabled": selector.publication_enabled(),
        "review_form": DiaryReviewForm(),
        "publication_delivery_summaries": (
            selector.list_publication_delivery_summaries(sheet["workflow"].pk)
            if sheet and sheet["workflow"] and _can_review(request.user)
            else []
        ),
    }
    if request.headers.get("HX-Request") and request.method == "POST" and sheet:
        return render(request, "student_diary/partials/daily_roster_card.html", context)
    return render(request, "student_diary/daily.html", context)


@login_required
def diary_student_history(request, student_id):
    """Exibe o histórico da criança autorizado pelo middleware."""
    from core.permissions import role_name

    selector = StudentDiarySelector()
    if role_name(request.user) == "GUARDIAN":
        if not selector.publication_enabled():
            raise PermissionDeniedError("Publicações da Agenda ainda não estão habilitadas.")
        published_history = selector.list_published_student_history(
            student_id, guardian_user_id=request.user.pk
        )
        student = published_history.first().student if published_history.exists() else None
        history = None
    else:
        history = selector.list_student_history(student_id)
        published_history = None
        student = history.first().student if history.exists() else None
    if student is None:
        from students.selectors import StudentSelector

        student = StudentSelector().get_by_id(student_id)
    return render(
        request,
        "student_diary/student_history.html",
        {"student": student, "history": history, "published_history": published_history},
    )


@login_required
def diary_publication_detail(request, entry_id):
    """Exibe ao responsável uma revisão publicada e sem controles de resposta."""
    selector = StudentDiarySelector()
    if not selector.publication_enabled():
        raise PermissionDeniedError("Publicações da Agenda ainda não estão habilitadas.")
    entry = selector.get_published_entry_for_guardian(entry_id, request.user.pk)
    return render(request, "student_diary/publication_detail.html", {"entry": entry})


@login_required
@require_POST
def diary_publication_mark_viewed(request, entry_id):
    """Registra a abertura automática após a renderização autenticada."""
    from django.http import HttpResponse

    from student_diary.workflow_services import DiaryWorkflowService

    DiaryWorkflowService(user=request.user).mark_entry_viewed(entry_id)
    return HttpResponse(status=204)


@login_required
@require_POST
def diary_sheet_submit(request, sheet_id):
    """Envia a folha para revisão."""
    from student_diary.workflow_services import DiaryWorkflowService

    sheet = DiaryWorkflowService(user=request.user).submit_sheet(
        sheet_id, base_url=request.build_absolute_uri("/").rstrip("/")
    )
    messages.success(request, "Agenda enviada para revisão.")
    return _workflow_redirect(sheet)


@login_required
@require_POST
def diary_sheet_approve(request, sheet_id):
    """Aprova e publica a revisão atual."""
    from student_diary.workflow_services import DiaryWorkflowService

    publication = DiaryWorkflowService(user=request.user).approve_sheet(
        sheet_id, base_url=request.build_absolute_uri("/").rstrip("/")
    )
    messages.success(request, "Agenda publicada e responsáveis notificados.")
    return _workflow_redirect(publication.sheet)


@login_required
@require_POST
def diary_sheet_request_changes(request, sheet_id):
    """Devolve a folha para correção."""
    from student_diary.workflow_services import DiaryWorkflowService

    form = DiaryReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Informe o motivo da devolução.")
        return redirect("diary_daily")
    sheet = DiaryWorkflowService(user=request.user).request_changes(
        sheet_id,
        form.cleaned_data["feedback"],
        base_url=request.build_absolute_uri("/").rstrip("/"),
    )
    messages.success(request, "Agenda devolvida para correção.")
    return _workflow_redirect(sheet)


@login_required
@require_POST
def diary_sheet_reopen(request, sheet_id):
    """Reabre uma publicação para gerar uma nova revisão."""
    from student_diary.workflow_services import DiaryWorkflowService

    sheet = DiaryWorkflowService(user=request.user).open_sheet_for_correction(sheet_id)
    messages.success(request, "Agenda reaberta. A publicação anterior foi preservada.")
    return _workflow_redirect(sheet)


def _can_review(user) -> bool:
    """Informa à interface se o usuário pode revisar; o service repete a validação."""
    from core.permissions import role_name

    return bool(getattr(user, "is_superuser", False) or role_name(user) in {"ADMIN", "COORDINATOR"})


def _workflow_redirect(sheet):
    """Retorna à turma e data da folha processada."""
    return redirect(
        f"{reverse('diary_daily')}?class_id={sheet.class_obj_id}&date={sheet.date.isoformat()}"
    )


@login_required
@access_policy("diary_configuration", VIEW)
def diary_configuration(request):
    """Lista os quatro aspectos predefinidos da rotina."""
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
@access_policy("diary_configuration", VIEW)
def diary_aspect_detail(request, category_id):
    """Exibe a ficha imutável de um aspecto e suas opções."""
    category = StudentDiarySelector().get_category_with_options(category_id)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "student_diary/partials/category_information_card.html",
            {"category": category},
        )
    return render(request, "student_diary/category_detail.html", {"category": category})


@login_required
@access_policy("diary_configuration", EDIT)
def diary_aspect_toggle(request, category_id):
    """Altera apenas a disponibilidade do aspecto na rotina."""
    category = StudentDiarySelector().get_category_with_options(category_id)
    form = RoutineAspectToggleForm(
        request.POST if request.method == "POST" else None,
        instance=category,
    )
    if request.method == "POST" and form.is_valid():
        category = StudentDiaryService(user=request.user).set_routine_aspect_enabled(
            category_id, form.cleaned_data["is_enabled"]
        )
        if request.headers.get("HX-Request"):
            return render(
                request,
                "student_diary/partials/category_information_card.html",
                {"category": category, "saved": True},
            )
        messages.success(request, "Aspecto da rotina atualizado.")
        return redirect("diary_aspect_detail", category_id=category_id)
    if not request.headers.get("HX-Request"):
        return redirect("diary_aspect_detail", category_id=category_id)
    return render(
        request,
        "partials/information_form_card.html",
        {
            "form": form,
            "component_id": "diary-category-information-card",
            "component_title": "Disponibilidade do aspecto",
            "edit_url": request.path,
            "cancel_url": (f"{request.path_info.removesuffix('ativacao/')}?component=information"),
        },
    )
