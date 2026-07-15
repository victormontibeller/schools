"""Views de autenticação e gestão de usuários."""

import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.forms import ChangePasswordForm, DemoSignupForm, LoginForm, UserEditForm
from accounts.selectors import AccountSelector
from accounts.services import AccountService
from base import context
from base.exceptions import (
    AppBaseError,
    BusinessRuleViolationError,
    PermissionDeniedError,
    ValidationError,
)
from base.forms import apply_validation_errors
from base.listing import build_querystring, build_sorting, resolve_listing_state
from base.media import private_file_response

logger = logging.getLogger(__name__)

USER_SORTS = {
    "name": "first_name",
    "-name": "-first_name",
    "email": "email",
    "-email": "-email",
    "created_at": "created_at",
    "-created_at": "-created_at",
}
PLATFORM_USER_SORTS = {
    "name": "first_name",
    "-name": "-first_name",
    "email": "email",
    "-email": "-email",
    "is_active": "is_active",
    "-is_active": "-is_active",
}


@login_required
def user_avatar(request, pk):
    """Entrega avatar privado ao próprio usuário ou a administrador autorizado."""
    user_obj = AccountSelector().get_by_id(pk)
    if request.user.pk != user_obj.pk and not request.user.is_superuser:
        from core.permissions import has_unrestricted_tenant_access

        if not has_unrestricted_tenant_access(request.user):
            raise PermissionDeniedError("Sem permissão para acessar este avatar.")
    if not user_obj.avatar:
        from base.exceptions import ObjectNotFoundError

        raise ObjectNotFoundError("UserAvatar", str(pk))
    return private_file_response(user_obj.avatar, as_attachment=False)


def demo_signup_view(request):
    """Cadastra conta temporária exclusivamente no tenant DEMO."""
    from django.core.cache import cache
    from django.urls import reverse

    form = DemoSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        throttle_key = f"demo-signup:{request.META.get('REMOTE_ADDR', '')}"
        attempts = cache.get(throttle_key, 0)
        if attempts >= 5:
            form.add_error(None, "Limite de cadastros atingido. Tente novamente mais tarde.")
        else:
            cache.set(throttle_key, attempts + 1, timeout=3600)
            try:
                AccountService().create_demo_user(
                    form.cleaned_data,
                    lambda token: request.build_absolute_uri(
                        reverse("demo_verify", kwargs={"token": token})
                    ),
                )
                return render(request, "auth/demo_signup_done.html")
            except ValidationError as exc:
                apply_validation_errors(form, exc)
            except BusinessRuleViolationError as exc:
                form.add_error(None, exc.message)
    return render(request, "auth/demo_signup.html", {"form": form})


def demo_verify_view(request, token):
    """Confirma o e-mail da conta DEMO e direciona ao login."""
    try:
        AccountService().verify_demo_user(token)
        messages.success(request, "E-mail confirmado. Sua conta DEMO está ativa por sete dias.")
    except BusinessRuleViolationError as exc:
        messages.error(request, exc.message)
    return redirect("login")


def teacher_invitation_view(request, token):
    """Permite ao professor convidado definir senha e ativar sua conta."""
    from accounts.forms import TeacherInvitationForm

    form = TeacherInvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            AccountService().activate_teacher_invitation(token, form.cleaned_data["password"])
            messages.success(request, "Conta ativada. Você já pode entrar.")
            return redirect("login")
        except (ValidationError, BusinessRuleViolationError) as exc:
            if isinstance(exc, ValidationError):
                for errors in exc.errors.values():
                    for error in errors:
                        form.add_error("password", error)
            else:
                form.add_error(None, exc.message)
    return render(request, "auth/teacher_invitation.html", {"form": form})


def login_view(request):
    """Autentica o usuário e inicia a sessão, redirecionando ao destino."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request, username=form.cleaned_data["email"], password=form.cleaned_data["password"]
        )
        if user is not None:
            login(request, user)
            if not form.cleaned_data["remember_me"]:
                request.session.set_expiry(0)
            logger.info(
                "Login bem-sucedido",
                extra={"user_id": str(user.pk), "correlation_id": context.correlation_id.get()},
            )
            next_url = request.GET.get("next", "")
            if not url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                from core.tenant_routing import is_platform_request

                next_url = "platform_dashboard" if is_platform_request(request) else "dashboard"
            return redirect(next_url)
        logger.warning("Login com falha", extra={"login_user_id": None})
        form.add_error(None, "E-mail ou senha inválidos.")
    return render(request, "auth/login.html", {"form": form})


@require_POST
def logout_view(request):
    """Encerra a sessão do usuário e redireciona para o login."""
    if request.user.is_authenticated:
        logout(request)
    return redirect("login")


@login_required
def profile_view(request):
    """Mantém a URL legada redirecionando para a ficha do usuário autenticado."""
    return redirect("user_detail", pk=request.user.pk)


@login_required
def change_password_view(request):
    """Processa a troca de senha do usuário autenticado."""
    form = ChangePasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            AccountService(user=request.user).change_password(
                request.user.pk,
                form.cleaned_data["current_password"],
                form.cleaned_data["new_password"],
            )
            messages.success(request, "Senha alterada com sucesso.")
            return redirect("user_detail", pk=request.user.pk)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
    return render(request, "accounts/change_password.html", {"form": form})


@login_required
def users_list_view(request):
    """Lista usuários paginados, renderizando parcial para HTMX quando aplicável."""
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="users_list",
        allowed_sorts=set(USER_SORTS),
        default_sort="name",
    )
    search = state["q"]
    sort = state["sort"]
    result = AccountSelector().list_users(search=search, order_by=USER_SORTS[sort], page=page)
    ctx = {
        "result": result,
        "q": search,
        "sort": sort,
        "sorting": build_sorting(
            current_sort=sort,
            search=search,
            sortable_fields=["name", "email", "created_at"],
        ),
        "list_query": build_querystring({"q": search, "sort": sort}),
        "clear_query": build_querystring({"q": "", "sort": "name"}, include_blank=True),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Usuários", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "accounts/partials/users_table.html", ctx)
    return render(request, "accounts/users_list.html", ctx)


@login_required
def user_detail_view(request, pk):
    """Exibe a ficha completa de um usuário."""
    user_obj = AccountSelector().get_by_id(pk)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "accounts/partials/user_information_card.html",
            {"user_obj": user_obj},
        )
    return render(request, "accounts/user_detail.html", {"user_obj": user_obj})


@login_required
def user_edit_view(request, pk):
    """Edita o usuário substituindo apenas o card de informações."""
    user_obj = AccountSelector().get_by_id(pk)
    form = UserEditForm(
        request.POST or None,
        request.FILES or None,
        initial={
            "first_name": user_obj.first_name,
            "email": user_obj.email,
            "last_name": user_obj.last_name,
            "phone": user_obj.phone,
            "role": user_obj.role,
            "is_active": user_obj.is_active,
        },
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        role = data.pop("role", None)
        data["role_id"] = role.pk if role else None
        try:
            user_obj = AccountService(user=request.user).update_user(pk, data)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        else:
            if request.headers.get("HX-Request"):
                return render(
                    request,
                    "accounts/partials/user_information_card.html",
                    {"user_obj": user_obj, "saved": True},
                )
            return redirect("user_detail", pk=pk)
    if not request.headers.get("HX-Request"):
        return redirect("user_detail", pk=pk)
    return render(
        request,
        "accounts/partials/user_information_form.html",
        {"form": form, "user_obj": user_obj},
    )


@login_required
def platform_user_list_view(request):
    """Lista operadores persistentes do schema público."""
    _require_platform_superuser(request)
    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="platform_users_list",
        allowed_sorts=set(PLATFORM_USER_SORTS),
        default_sort="name",
    )
    search = state["q"]
    sort = state["sort"]
    context = {
        "result": AccountSelector().list_platform_users(
            search=search,
            order_by=PLATFORM_USER_SORTS[sort],
            page=page,
        ),
        "q": search,
        "sort": sort,
        "sorting": build_sorting(
            current_sort=sort,
            search=search,
            sortable_fields=["name", "email", "is_active"],
        ),
        "list_query": build_querystring({"q": search, "sort": sort}),
        "breadcrumb_items": [
            {"label": "Plataforma", "url": "platform_dashboard"},
            {"label": "Operadores", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "accounts/partials/platform_users_table.html", context)
    return render(request, "accounts/platform_users_list.html", context)


@login_required
def platform_user_create_view(request):
    """Cadastra operador do painel público."""
    _require_platform_superuser(request)
    from accounts.forms import PlatformUserCreateForm

    form = PlatformUserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            AccountService(user=request.user).create_platform_user(form.cleaned_data)
            messages.success(request, "Operador cadastrado com sucesso.")
            return redirect("platform_user_list")
        except AppBaseError as exc:
            _apply_platform_form_error(form, exc)
    return render(
        request,
        "accounts/platform_user_form.html",
        {"form": form, "title": "Novo Operador"},
    )


@login_required
def platform_user_edit_view(request, pk):
    """Edita permissões básicas de operador público."""
    _require_platform_superuser(request)
    from accounts.forms import PlatformUserEditForm

    user_obj = AccountSelector().get_platform_user(pk)
    form = PlatformUserEditForm(
        request.POST or None,
        initial={
            "first_name": user_obj.first_name,
            "last_name": user_obj.last_name,
            "is_active": user_obj.is_active,
            "is_superuser": user_obj.is_superuser,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            AccountService(user=request.user).update_platform_user(pk, form.cleaned_data)
            messages.success(request, "Operador atualizado com sucesso.")
            return redirect("platform_user_list")
        except AppBaseError as exc:
            _apply_platform_form_error(form, exc)
    return render(
        request,
        "accounts/platform_user_form.html",
        {"form": form, "title": "Editar Operador", "user_obj": user_obj},
    )


def _require_platform_superuser(request) -> None:
    """Restringe gestão de operadores ao painel público."""
    from core.tenant_routing import is_platform_request

    if not is_platform_request(request) or not request.user.is_superuser:
        raise PermissionDeniedError("Sem permissão para administrar operadores.")


def _apply_platform_form_error(form, exc: AppBaseError) -> None:
    """Converte exceção de aplicação em erros do formulário."""
    errors = getattr(exc, "errors", None)
    if errors:
        for field, messages_list in errors.items():
            for error in messages_list:
                form.add_error(field, error)
        return
    form.add_error(None, exc.message)
