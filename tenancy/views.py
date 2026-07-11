"""Views de acesso temporário de operadores da plataforma."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from base.exceptions import AppBaseError, PermissionDeniedError


@login_required
def platform_dashboard(request: HttpRequest) -> HttpResponse:
    """Exibe o painel administrativo do schema público."""
    from core.tenant_routing import is_platform_request
    from tenancy.selectors import SchoolSelector

    if not request.user.is_staff:
        raise PermissionDeniedError("Sem permissão para administrar a plataforma.")
    if not is_platform_request(request):
        raise PermissionDeniedError("O painel da plataforma exige o domínio administrativo.")

    page = int(request.GET.get("page", 1))
    selector = SchoolSelector()
    return render(
        request,
        "tenancy/platform_dashboard.html",
        {
            "overview": selector.get_platform_overview(),
            "result": selector.list_platform_tenants(page=page),
        },
    )


@login_required
def platform_school_list(request: HttpRequest) -> HttpResponse:
    """Lista escolas provisionadas no catálogo público."""
    _require_platform_superuser(request)
    from tenancy.selectors import SchoolSelector

    page = int(request.GET.get("page", 1))
    search = request.GET.get("q", "").strip()
    context = {
        "result": SchoolSelector().list_platform_tenants(search=search, page=page),
        "q": search,
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
def support_access_create(request: HttpRequest) -> HttpResponse:
    """Exibe e processa a criação de concessão no schema público."""
    from tenancy.forms import SupportAccessForm
    from tenancy.services import SupportAccessService, support_target_url

    if not (request.user.is_superuser or request.user.has_perm("tenancy.access_tenant")):
        raise PermissionDeniedError("Sem permissão para acessar tenants.")
    form = SupportAccessForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            grant, token = SupportAccessService(user=request.user).create_grant(
                form.cleaned_data["tenant_id"],
                form.cleaned_data["reason"],
                request.META.get("REMOTE_ADDR", ""),
            )
            return redirect(support_target_url(grant, token))
        except AppBaseError as exc:
            messages.error(request, exc.message)
    return render(request, "tenancy/support_access_form.html", {"form": form})


def support_access_consume(request: HttpRequest) -> HttpResponse:
    """Consome token no domínio do tenant e autentica a conta técnica."""
    from tenancy.services import SupportAccessService

    tenant = getattr(request, "tenant", None)
    schema = getattr(tenant, "schema_name", "public")
    grant, support_user = SupportAccessService().consume_grant(request.GET.get("token", ""), schema)
    login(request, support_user, backend="core.auth_backends.RolePermissionBackend")
    request.session["platform_actor_id"] = str(grant.operator_id)
    request.session["support_grant_id"] = str(grant.pk)
    request.session["support_expires_at"] = grant.expires_at.isoformat()
    return redirect("dashboard")


@require_POST
@login_required
def support_access_end(request: HttpRequest) -> HttpResponse:
    """Encerra concessão e remove a sessão técnica."""
    from tenancy.services import SupportAccessService

    grant_id = request.session.get("support_grant_id")
    if grant_id:
        SupportAccessService(user=request.user).end_grant(grant_id)
    logout(request)
    return redirect("index")
