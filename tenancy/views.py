"""Views do catálogo público de escolas."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from base.exceptions import AppBaseError, PermissionDeniedError
from base.listing import resolve_listing_state


@login_required
def platform_dashboard(request: HttpRequest) -> HttpResponse:
    """Exibe o painel administrativo do schema público."""
    from core.tenant_routing import is_platform_request
    from tenancy.selectors import SchoolSelector

    if not request.user.is_staff:
        raise PermissionDeniedError("Sem permissão para administrar a plataforma.")
    if not is_platform_request(request):
        raise PermissionDeniedError("O painel da plataforma exige o domínio administrativo.")

    state = resolve_listing_state(
        request,
        scope="platform_dashboard",
        allowed_sorts={"name"},
        default_sort="name",
    )
    selector = SchoolSelector()
    return render(
        request,
        "tenancy/platform_dashboard.html",
        {
            "overview": selector.get_platform_overview(),
            "result": selector.list_platform_tenants(page=state["page"]),
        },
    )


@login_required
def platform_school_list(request: HttpRequest) -> HttpResponse:
    """Lista escolas provisionadas no catálogo público."""
    _require_platform_superuser(request)
    from tenancy.selectors import SchoolSelector

    state = resolve_listing_state(
        request,
        scope="platform_school_list",
        allowed_sorts={"name"},
        default_sort="name",
    )
    context = {
        "result": SchoolSelector().list_platform_tenants(search=state["q"], page=state["page"]),
        "q": state["q"],
    }
    if request.headers.get("HX-Request"):
        return render(request, "tenancy/partials/platform_schools_table.html", context)
    return render(request, "tenancy/platform_school_list.html", context)


@login_required
def platform_school_create(request: HttpRequest) -> HttpResponse:
    """Provisiona escola e domínio primário."""
    _require_platform_superuser(request)
    from tenancy.forms import PlatformSchoolCreateForm
    from tenancy.services import PlatformSchoolService

    form = PlatformSchoolCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            PlatformSchoolService(user=request.user).create_platform_school(form.cleaned_data)
            messages.success(request, "Escola provisionada com sucesso.")
            return redirect("platform_school_list")
        except AppBaseError as exc:
            _apply_form_error(form, exc)
    return render(
        request,
        "tenancy/platform_school_form.html",
        {"form": form, "title": "Nova Escola"},
    )


@login_required
def platform_school_edit(request: HttpRequest, pk) -> HttpResponse:
    """Edita catálogo e domínio primário de uma escola."""
    _require_platform_superuser(request)
    from tenancy.forms import PlatformSchoolEditForm
    from tenancy.selectors import SchoolSelector
    from tenancy.services import PlatformSchoolService

    school = SchoolSelector().get_platform_school(pk)
    primary_domain = next((item for item in school.domains.all() if item.is_primary), None)
    initial = {
        "name": school.name,
        "domain": getattr(primary_domain, "domain", ""),
        "email": school.email,
        "phone": school.phone,
        "is_active": school.is_active and not school.deleted_at,
        "diary_enabled": (school.settings or {})
        .get("student_diary", {})
        .get("interactive_enabled", False),
        "resend_domain": (school.settings or {}).get("email", {}).get("resend_domain", ""),
        "resend_from_email": (school.settings or {}).get("email", {}).get("from_email", ""),
        "resend_verified": (school.settings or {}).get("email", {}).get("resend_verified", False),
    }
    form = PlatformSchoolEditForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            PlatformSchoolService(user=request.user).update_platform_school(
                school.pk, form.cleaned_data
            )
            messages.success(request, "Escola atualizada com sucesso.")
            return redirect("platform_school_list")
        except AppBaseError as exc:
            _apply_form_error(form, exc)
    return render(
        request,
        "tenancy/platform_school_form.html",
        {"form": form, "title": "Editar Escola", "school": school},
    )


def _require_platform_superuser(request: HttpRequest) -> None:
    """Bloqueia gestão do catálogo fora do schema público ou sem superusuário."""
    from core.tenant_routing import is_platform_request

    if not is_platform_request(request) or not request.user.is_superuser:
        raise PermissionDeniedError("Sem permissão para administrar a plataforma.")


def _apply_form_error(form, exc: AppBaseError) -> None:
    """Converte exceções de aplicação em erros de formulário."""
    errors = getattr(exc, "errors", None)
    if errors:
        for field, messages_list in errors.items():
            for error in messages_list:
                form.add_error(field, error)
        return
    form.add_error(None, exc.message)


@login_required
def platform_school_bootstrap(request, pk):
    """Solicita o bootstrap ou reenvio do primeiro convite administrativo."""
    _require_platform_superuser(request)
    from accounts.staff_forms import BootstrapAdministratorForm
    from tenancy.selectors import SchoolSelector
    from tenancy.services import PlatformSchoolService

    school = SchoolSelector().get_platform_school(pk)
    form = BootstrapAdministratorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            PlatformSchoolService(user=request.user).create_school_administrator(
                pk, form.cleaned_data
            )
        except AppBaseError as exc:
            _apply_form_error(form, exc)
        else:
            messages.success(request, "Primeiro acesso preparado. Convite agendado para envio.")
            return redirect("platform_school_edit", pk=pk)
    return render(
        request,
        "tenancy/platform_school_form.html",
        {
            "form": form,
            "title": "Convidar primeiro administrador",
            "school": school,
        },
    )
