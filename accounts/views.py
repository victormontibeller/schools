"""Views de autenticação e gestão de usuários."""

import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.forms import ChangePasswordForm, LoginForm, UserEditForm
from accounts.selectors import AccountSelector
from accounts.services import AccountService
from base import context
from base.exceptions import ValidationError
from base.listing import build_querystring, build_sorting, resolve_listing_state

logger = logging.getLogger(__name__)

USER_SORTS = {
    "name": "first_name",
    "-name": "-first_name",
    "email": "email",
    "-email": "-email",
    "created_at": "created_at",
    "-created_at": "-created_at",
}


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
            return redirect(request.GET.get("next", "school_dashboard"))
        logger.warning("Login com falha", extra={"login_user_id": None})
        form.add_error(None, "E-mail ou senha inválidos.")
    return render(request, "auth/login.html", {"form": form})


def logout_view(request):
    """Encerra a sessão do usuário e redireciona para o login."""
    if request.user.is_authenticated:
        logout(request)
    return redirect("login")


@login_required
def profile_view(request):
    """Exibe o perfil do usuário autenticado."""
    return render(request, "accounts/profile.html", {"user_obj": request.user})


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
            return redirect("profile")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field, error)
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
        initial={
            "first_name": user_obj.first_name,
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
        user_obj = AccountService(user=request.user).update_user(pk, data)
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
        "partials/information_form_card.html",
        {
            "form": form,
            "component_id": "user-information-card",
            "component_title": "Informações da Pessoa",
            "edit_url": request.path,
            "cancel_url": f"{request.path_info.removesuffix('editar/')}?component=information",
        },
    )
