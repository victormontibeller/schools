"""Health check, landing page publica, dashboard principal e error handlers."""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from base import context

logger = logging.getLogger(__name__)


def _is_testing() -> bool:
    """Retorna True quando rodando sob pytest (settings.TESTING)."""
    from django.conf import settings

    return bool(getattr(settings, "TESTING", False))


# ── Textos da landing page (mantidos fora das views para legibilidade) ────────
_LANDING_FEATURES = [
    {
        "icon": "feather-layers",
        "title": "Turmas & Matrículas",
        "desc": (
            "Organize turmas por ano letivo, série e turno. "
            "Controle de vagas, transferências e histórico de matrículas."
        ),
    },
    {
        "icon": "feather-book-open",
        "title": "Professores & Disciplinas",
        "desc": (
            "Cadastro de professores, atribuição de disciplinas e gestão de "
            "carga horária num só lugar."
        ),
    },
    {
        "icon": "feather-clock",
        "title": "Grade Horária",
        "desc": "Monte a grade semanal com prevenção automática de conflitos de professor e sala.",
    },
    {
        "icon": "feather-edit-3",
        "title": "Atividades & Notas",
        "desc": (
            "Crie provas, trabalhos e tarefas. Lance notas em lote com " "feedback individualizado."
        ),
    },
    {
        "icon": "feather-shield",
        "title": "Dados protegidos por escola",
        "desc": (
            "Cada instituição trabalha em um espaço isolado, com permissões "
            "e histórico de alterações."
        ),
    },
    {
        "icon": "feather-bar-chart-2",
        "title": "Visão e rastreabilidade",
        "desc": (
            "Indicadores operacionais e registros de auditoria ajudam a equipe "
            "a acompanhar decisões e mudanças."
        ),
    },
]

_LANDING_PLANS = [
    {
        "name": "Essencial",
        "price": "R$ 299",
        "period": "/mês",
        "highlight": False,
        "description": "Para organizar a rotina de uma unidade escolar.",
        "cta_label": "Testar por 7 dias",
        "cta_url": "demo_signup",
        "features": [
            "1 escola (tenant)",
            "Até 300 alunos",
            "Professores, turmas e grade horária",
            "Suporte por e-mail",
        ],
    },
    {
        "name": "Profissional",
        "price": "R$ 699",
        "period": "/mês",
        "highlight": True,
        "description": "Para escolas que querem uma operação acadêmica completa.",
        "cta_label": "Testar por 7 dias",
        "cta_url": "demo_signup",
        "features": [
            "3 escolas (tenants)",
            "Alunos ilimitados",
            "Atividades, notas e relatórios",
            "Comunicados e notificações por e-mail",
            "Suporte prioritário",
        ],
    },
    {
        "name": "Rede",
        "price": "Sob consulta",
        "period": "",
        "highlight": False,
        "description": "Para redes que precisam de visão consolidada e implantação acompanhada.",
        "cta_label": "Falar com especialista",
        "cta_href": "mailto:contato@schoolmanager.dev?subject=Plano%20Rede",
        "features": [
            "Escolas ilimitadas",
            "Dashboards executivos e visão multi-escola",
            "Perfis de acesso e auditoria centralizada",
            "Onboarding dedicado",
            "Suporte para implantação",
        ],
    },
]

_LANDING_FAQS = [
    {
        "q": "Preciso instalar algo na escola?",
        "a": (
            "Não. A plataforma é 100% em nuvem — acessa pelo navegador em "
            "qualquer dispositivo. Sem servidores para manter."
        ),
    },
    {
        "q": "Meus dados ficam separados dos de outras escolas?",
        "a": (
            "Sim. Cada escola utiliza um schema PostgreSQL isolado — as informações "
            "de uma instituição não se misturam com as de outra."
        ),
    },
    {
        "q": "Consigo migrar de outro sistema?",
        "a": (
            "A plataforma possui importação de alunos via CSV. Outros dados "
            "podem ser avaliados com a equipe durante a implantação."
        ),
    },
    {
        "q": "Tem teste grátis?",
        "a": (
            "Sim. Crie seu acesso ao ambiente demonstrativo e explore os principais "
            "fluxos por sete dias antes de decidir."
        ),
    },
]


def health(request: HttpRequest) -> HttpResponse:
    """Liveness pública sem detalhes internos de infraestrutura."""
    return HttpResponse(
        content=json.dumps({"status": "ok"}),
        content_type="application/json",
        status=200,
    )


def readiness(request: HttpRequest) -> HttpResponse:
    """Readiness protegida que verifica dependências sem vazar exceções."""
    from django.conf import settings

    expected = getattr(settings, "READINESS_TOKEN", "")
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if (not expected or supplied != expected) and not getattr(request.user, "is_staff", False):
        return HttpResponse(status=403)
    checks: dict[str, str] = {}
    overall = "ok"
    status_code = 200

    # Banco de dados
    try:
        from django.db import connection

        connection.ensure_connection()
        checks["db"] = "ok"
    except Exception:  # noqa: BLE001
        checks["db"] = "error"
        overall = "degraded"
        status_code = 503

    # Redis — opcional (apenas se o backend de cache for Redis)
    try:
        from django.core.cache import cache

        cache.set("health:probe", "1", timeout=5)
        checks["redis"] = "ok" if cache.get("health:probe") == "1" else "stale"
    except Exception:  # noqa: BLE001
        checks["redis"] = "error"
        overall = "degraded"
        status_code = 503

    # RabbitMQ — opcional: tentativa curta; em testes, ignoramos para não
    #  introduzir latência de connect no broker inexistente.
    if _is_testing():
        checks["rabbitmq"] = "skipped"
    else:
        try:
            from core.celery import app as celery_app  # noqa: PLC0415

            conn = celery_app.connection_for_read(timeout=1)
            conn.ensure_connection(max_retries=0)
            conn.close()
            checks["rabbitmq"] = "ok"
        except Exception:  # noqa: BLE001
            checks["rabbitmq"] = "skipped"

    body = {"status": overall, "checks": checks}
    return HttpResponse(
        content=json.dumps(body, ensure_ascii=False),
        content_type="application/json",
        status=status_code,
    )


def metrics(request: HttpRequest) -> HttpResponse:
    """Exposição de métricas Prometheus.

    Em produção, deve ser protegido por Traefik/basic-auth ou `staff_member_required`.
    Aqui deixamos o django_prometheus responder; em DEBUG, qualquer cliente pode
    acessar; fora de DEBUG, exigimos `is_staff`.
    """
    from django.conf import settings

    expected = getattr(settings, "METRICS_TOKEN", "")
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
    is_staff = getattr(request.user, "is_staff", False)
    if (
        not getattr(settings, "DEBUG", False)
        and not is_staff
        and (not expected or supplied != expected)
    ):
        return HttpResponse(status=403)

    from django_prometheus import exports  # noqa: PLC0415

    return exports.ExportToDjangoView(request)


def index(request: HttpRequest) -> HttpResponse:
    """Landing page pública de vendas do SaaS.

    Não exige login — apresenta a plataforma a escolas potenciais e os
    direciona para o login/assinatura. Usuários já autenticados são
    encaminhados direto ao dashboard.
    """
    if request.user.is_authenticated:
        from core.tenant_routing import is_platform_request

        target = "platform_dashboard" if is_platform_request(request) else "dashboard"
        return redirect(target)

    return render(
        request,
        "landing.html",
        {
            "features": _LANDING_FEATURES,
            "plans": _LANDING_PLANS,
            "faqs": _LANDING_FAQS,
        },
    )


def _detect_dashboard_role(user) -> str:
    """Determina o perfil operacional para a home interna."""
    if hasattr(user, "teacher_profile"):
        return "TEACHER"
    if hasattr(user, "guardian_profile"):
        return "GUARDIAN"
    if user.role_id and user.role:
        return user.role.name
    if user.is_staff:
        return "ADMIN"
    return "COORDINATOR"


def _dashboard_quick_actions(role_name: str) -> list[dict[str, str]]:
    """Retorna atalhos prioritarios conforme o perfil do usuario."""
    quick_actions_map = {
        "ADMIN": [
            {"label": "Novo aluno", "url": "student_create", "icon": "feather-user-plus"},
            {"label": "Novo professor", "url": "teacher_create", "icon": "feather-user-check"},
            {"label": "Nova turma", "url": "class_create", "icon": "feather-layers"},
            {"label": "Usuários", "url": "users_list", "icon": "feather-users"},
        ],
        "COORDINATOR": [
            {"label": "Novo aluno", "url": "student_create", "icon": "feather-user-plus"},
            {"label": "Novo professor", "url": "teacher_create", "icon": "feather-user-check"},
            {"label": "Nova turma", "url": "class_create", "icon": "feather-layers"},
            {"label": "Calendário", "url": "calendar_month", "icon": "feather-calendar"},
        ],
        "TEACHER": [
            {"label": "Minhas disciplinas", "url": "teachers_list", "icon": "feather-book-open"},
            {"label": "Atividades", "url": "activities_list", "icon": "feather-edit-3"},
            {
                "label": "Lançar frequência",
                "url": "attendance_records_list",
                "icon": "feather-check-circle",
            },
            {"label": "Agenda", "url": "time_slots_list", "icon": "feather-clock"},
        ],
        "GUARDIAN": [
            {"label": "Dados do aluno", "url": "students_list", "icon": "feather-user"},
            {"label": "Calendário", "url": "calendar_month", "icon": "feather-calendar"},
            {"label": "Comunicados", "url": "announcement_list", "icon": "feather-bell"},
            {"label": "Meu perfil", "url": "profile", "icon": "feather-settings"},
        ],
    }
    return quick_actions_map.get(role_name, quick_actions_map["COORDINATOR"])


def _dashboard_greeting() -> str:
    """Retorna uma saudacao curta conforme o horario local."""
    from django.utils import timezone

    hour = timezone.localtime().hour
    if hour < 12:
        return "Bom dia"
    if hour < 18:
        return "Boa tarde"
    return "Boa noite"


def _dashboard_role_label(user, role_name: str) -> str:
    """Retorna o rotulo amigavel do perfil exibido na home."""
    if user.role_id and user.role:
        return str(user.role)
    labels = {
        "ADMIN": "Administrador",
        "COORDINATOR": "Coordenador",
        "TEACHER": "Professor",
        "GUARDIAN": "Responsável",
    }
    return labels.get(role_name, "Usuário")


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Exibe o painel operacional canonico da escola."""
    from core.tenant_routing import is_platform_request

    if is_platform_request(request):
        return redirect("platform_dashboard")

    from core.permissions import can_access_module
    from dashboard.services import DashboardService

    role_name = _detect_dashboard_role(request.user)
    data = DashboardService(user=request.user).get_school_dashboard_data()
    can_view_financial = can_access_module(request.user, "financeiro")
    return render(
        request,
        "dashboard.html",
        {
            "data": data,
            "quick_actions": _dashboard_quick_actions(role_name),
            "role_name": _dashboard_role_label(request.user, role_name),
            "greeting": _dashboard_greeting(),
            "can_view_financial": can_view_financial,
            "has_visible_attention": bool(
                data["students_at_risk"]
                or data["pending_activities"]
                or (can_view_financial and data["financial_kpis"]["total_vencido"])
            ),
        },
    )


# ── Tela da Empresa ──────────────────────────────────────────────────────────


@login_required
def business_unit_list(request: HttpRequest) -> HttpResponse:
    """Lista unidades de negócio do tenant ativo."""
    from base.listing import build_querystring, build_sorting, resolve_listing_state
    from core.selectors import BusinessUnitSelector

    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="business_unit_list",
        allowed_sorts={"name", "-name", "cnpj", "-cnpj", "phone", "-phone", "email", "-email"},
        default_sort="name",
    )
    search, sort = state["q"], state["sort"]
    result = BusinessUnitSelector().list_business_units(search=search, order_by=sort, page=page)
    ctx = {
        "result": result,
        "q": search,
        "sort": sort,
        "sorting": build_sorting(
            current_sort=sort, search=search, sortable_fields=["name", "cnpj", "phone", "email"]
        ),
        "list_query": build_querystring({"q": search, "sort": sort}),
        "clear_query": build_querystring({"q": "", "sort": "name"}, include_blank=True),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Unidades", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "core/partials/business_units_table.html", ctx)
    return render(request, "core/business_units_list.html", ctx)


@login_required
def business_unit_detail(request: HttpRequest, pk) -> HttpResponse:
    """Exibe a ficha completa de uma unidade de negocio."""
    from addresses.selectors import AddressSelector
    from core.selectors import BusinessUnitSelector

    business_unit = BusinessUnitSelector().get_by_id(pk)
    addresses = AddressSelector().get_by_entity("business_unit", business_unit.pk)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "core/partials/business_unit_information_card.html",
            {"business_unit": business_unit},
        )
    return render(
        request,
        "core/business_unit_detail.html",
        {"business_unit": business_unit, "addresses": addresses},
    )


@login_required
def business_unit_create(request: HttpRequest) -> HttpResponse:
    """Processa o formulario de criacao de empresa."""
    from django.contrib import messages

    from base.exceptions import BusinessRuleViolationError, ValidationError
    from core.forms import BusinessUnitForm
    from core.services import BusinessUnitService

    form = BusinessUnitForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            logo = data.pop("logo", None)
            business_unit = BusinessUnitService(user=request.user).create_business_unit(data)
            if logo:
                BusinessUnitService(user=request.user).update_business_unit_logo(
                    business_unit.pk, logo
                )
            messages.success(request, "Empresa criada com sucesso.")
            return redirect("business_unit_detail", pk=business_unit.pk)
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)

    return render(
        request,
        "core/business_unit_form.html",
        {"form": form, "title": "Nova Empresa"},
    )


@login_required
def business_unit_edit(request: HttpRequest, pk) -> HttpResponse:
    """Processa o formulario de edicao de empresa."""
    from django.contrib import messages

    from base.exceptions import BusinessRuleViolationError, ValidationError
    from core.forms import BusinessUnitForm
    from core.selectors import BusinessUnitSelector
    from core.services import BusinessUnitService

    business_unit = BusinessUnitSelector().get_by_id(pk)

    if request.method == "POST":
        form = BusinessUnitForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                data = form.cleaned_data.copy()
                logo = data.pop("logo", None)
                BusinessUnitService(user=request.user).update_business_unit(pk, data)
                if logo:
                    BusinessUnitService(user=request.user).update_business_unit_logo(pk, logo)
                business_unit = BusinessUnitSelector().get_by_id(pk)
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "core/partials/business_unit_information_card.html",
                        {"business_unit": business_unit, "saved": True},
                    )
                messages.success(request, "Empresa atualizada com sucesso.")
                return redirect("business_unit_detail", pk=pk)
            except ValidationError as exc:
                for field, errors in exc.errors.items():
                    for error in errors:
                        form.add_error(field if field != "__all__" else None, error)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        form = BusinessUnitForm(
            initial={
                "name": business_unit.name,
                "legal_name": business_unit.legal_name,
                "trade_name": business_unit.trade_name,
                "cnpj": business_unit.cnpj or "",
                "state_registration": business_unit.state_registration,
                "municipal_registration": business_unit.municipal_registration,
                "phone": business_unit.phone,
                "email": business_unit.email,
                "contact_full_name": business_unit.contact_full_name,
                "contact_role": business_unit.contact_role,
                "contact_phone": business_unit.contact_phone,
                "contact_email": business_unit.contact_email,
                "academic_year_start": business_unit.academic_year_start,
                "academic_year_end": business_unit.academic_year_end,
            }
        )

    if not request.headers.get("HX-Request"):
        return render(
            request,
            "core/business_unit_form.html",
            {"form": form, "title": "Editar Unidade", "instance": business_unit},
        )
    return render(
        request,
        "core/partials/organization_information_form.html",
        {
            "form": form,
            "component_id": "business-unit-information-card",
            "component_title": "Informações da Unidade",
            "edit_url": request.path,
            "cancel_url": f"{request.path_info.removesuffix('editar/')}?component=information",
            "organization": business_unit,
        },
    )


@login_required
def school_detail(request: HttpRequest) -> HttpResponse:
    """Exibe os dados institucionais da empresa do tenant ativo."""
    from django.contrib import messages

    from addresses.selectors import AddressSelector
    from core.selectors import SchoolSelector

    school = SchoolSelector().get_current_school()
    if not school:
        messages.error(request, "Escola nao encontrada no tenant ativo.")
        return redirect("business_unit_list")

    addresses = AddressSelector().get_by_entity("school", school.pk)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "core/partials/school_information_card.html",
            {"school": school},
        )
    return render(
        request,
        "core/school_detail.html",
        {"school": school, "addresses": addresses},
    )


@login_required
def school_edit(request: HttpRequest) -> HttpResponse:
    """Tela de edicao dos dados da empresa (escola)."""
    from django.contrib import messages

    from base.exceptions import BusinessRuleViolationError, ValidationError
    from core.forms import SchoolEditForm
    from core.selectors import SchoolSelector
    from core.services import SchoolService

    school = SchoolSelector().get_current_school()
    if not school:
        messages.error(request, "Escola nao encontrada no tenant ativo.")
        return redirect("business_unit_list")

    if request.method == "POST":
        form = SchoolEditForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                service = SchoolService(user=request.user)
                data = form.cleaned_data.copy()

                # Tratar logo separadamente
                logo = data.pop("logo", None)
                service.update_school(school.pk, data)

                if logo:
                    service.update_logo(school.pk, logo)

                school = SchoolSelector().get_current_school()
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "core/partials/school_information_card.html",
                        {"school": school, "saved": True},
                    )
                messages.success(request, "Configurações da escola atualizadas com sucesso.")
                return redirect("school_settings_detail")
            except ValidationError as exc:
                for field, errors in exc.errors.items():
                    form.add_error(field, errors)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        initial = {
            "name": school.name,
            "legal_name": school.legal_name,
            "trade_name": school.trade_name,
            "cnpj": school.cnpj or "",
            "state_registration": school.state_registration,
            "municipal_registration": school.municipal_registration,
            "phone": school.phone,
            "email": school.email,
            "contact_full_name": school.contact_full_name,
            "contact_role": school.contact_role,
            "contact_phone": school.contact_phone,
            "contact_email": school.contact_email,
            "academic_year_start": school.academic_year_start,
            "academic_year_end": school.academic_year_end,
        }
        form = SchoolEditForm(initial=initial)

    if not request.headers.get("HX-Request"):
        return render(
            request,
            "core/school_form.html",
            {
                "form": form,
                "school": school,
                "title": "Editar Escola",
                "instance": school,
            },
        )
    return render(
        request,
        "core/partials/organization_information_form.html",
        {
            "form": form,
            "component_id": "school-information-card",
            "component_title": "Informações da Escola",
            "edit_url": request.path,
            "cancel_url": f"{reverse('school_settings_detail')}?component=information",
            "organization": school,
        },
    )


# ── Error handlers ───────────────────────────────────────────────────────────


def handler404(request: HttpRequest, exception=None) -> HttpResponse:
    """Pagina 404 personalizada com correlation_id."""
    cid = context.correlation_id.get() or "-"
    return render(
        request,
        "errors/404.html",
        {"correlation_id": cid},
        status=404,
    )


def handler500(request: HttpRequest) -> HttpResponse:
    """Pagina 500 personalizada com correlation_id e log estruturado."""
    cid = context.correlation_id.get() or "-"
    logger.critical(
        "Erro interno do servidor (500)",
        extra={
            "correlation_id": cid,
            "path": request.path,
            "method": request.method,
        },
    )
    return render(
        request,
        "errors/500.html",
        {"correlation_id": cid},
        status=500,
    )
