"""Health check, landing page publica, dashboard principal e error handlers."""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

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
        "title": "Multi-escola Seguro",
        "desc": (
            "Isolamento por schema PostgreSQL — cada escola enxerga apenas os "
            "próprios dados, com auditoria completa."
        ),
    },
    {
        "icon": "feather-bar-chart-2",
        "title": "Auditoria & Observabilidade",
        "desc": (
            "Toda operação é registrada com usuário, IP e correlation ID. "
            "Logs estruturados prontos para produção."
        ),
    },
]

_LANDING_PLANS = [
    {
        "name": "Essencial",
        "price": "R$ 299",
        "period": "/mês",
        "highlight": False,
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
        "features": [
            "3 escolas (tenants)",
            "Alunos ilimitados",
            "Atividades, notas e relatórios",
            "Notificações por e-mail e WhatsApp",
            "Suporte prioritário",
        ],
    },
    {
        "name": "Rede",
        "price": "Sob consulta",
        "period": "",
        "highlight": False,
        "features": [
            "Escolas ilimitadas",
            "Dashboards executivos",
            "SSO/LDAP e API",
            "Onboarding dedicado",
            "SLA garantido",
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
            "Sim. Cada escola roda em um schema PostgreSQL isolado — nenhuma "
            "informação crossinga tenants, por projeto."
        ),
    },
    {
        "q": "Consigo migrar de outro sistema?",
        "a": (
            "Sim. Importamos alunos e professores via CSV/planilha, e "
            "aceleramos o cadastro inicial assim que você assina."
        ),
    },
    {
        "q": "Tem teste grátis?",
        "a": (
            "Você pode experimentar o ambiente de demonstração agora mesmo e "
            "solicitar 14 dias grátis antes de assinar."
        ),
    },
]


def health(request: HttpRequest) -> HttpResponse:
    """Endpoint de health check que verifica conectividade com banco, Redis e RabbitMQ.

    Em modo de testes (SQLite in-memory + Django cache dummy), as checagens de
    Redis/RabbitMQ são puladas para manter o health autônomo.
    """
    checks: dict[str, str] = {}
    overall = "ok"
    status_code = 200

    # Banco de dados
    try:
        from django.db import connection

        connection.ensure_connection()
        checks["db"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["db"] = f"error: {exc}"
        overall = "degraded"
        status_code = 503

    # Redis — opcional (apenas se o backend de cache for Redis)
    try:
        from django.core.cache import cache

        cache.set("health:probe", "1", timeout=5)
        checks["redis"] = "ok" if cache.get("health:probe") == "1" else "stale"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"
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

    if not getattr(settings, "DEBUG", False) and not request.user.is_staff:
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
        return redirect("school_dashboard")

    return render(
        request,
        "landing.html",
        {
            "features": _LANDING_FEATURES,
            "plans": _LANDING_PLANS,
            "faqs": _LANDING_FAQS,
        },
    )


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Exibe o dashboard com atalhos para os módulos principais e próximos eventos."""
    from academic_calendar.selectors import CalendarSelector

    modules = [
        {"name": "Empresa", "url": "school_detail", "icon": "feather-briefcase"},
        {"name": "Professores", "url": "teachers_list", "icon": "feather-book-open"},
        {"name": "Disciplinas", "url": "subjects_list", "icon": "feather-book"},
        {"name": "Alunos", "url": "students_list", "icon": "feather-user-check"},
        {"name": "Responsáveis", "url": "guardians_list", "icon": "feather-heart"},
        {"name": "Turmas", "url": "classes_list", "icon": "feather-layers"},
        {"name": "Salas", "url": "rooms_list", "icon": "feather-home"},
        {"name": "Atividades", "url": "activities_list", "icon": "feather-edit-3"},
        {"name": "Frequência", "url": "attendance_records_list", "icon": "feather-check-circle"},
        {"name": "Horários", "url": "time_slots_list", "icon": "feather-clock"},
        {"name": "Calendário", "url": "calendar_month", "icon": "feather-calendar"},
        {"name": "Usuários", "url": "users_list", "icon": "feather-users"},
    ]
    upcoming = CalendarSelector().get_upcoming_events(days=7)[:5]
    return render(request, "dashboard.html", {"modules": modules, "upcoming": upcoming})


# ── Tela da Empresa ──────────────────────────────────────────────────────────


@login_required
def school_detail(request: HttpRequest) -> HttpResponse:
    """Exibe os dados institucionais da empresa do tenant ativo."""
    from django.contrib import messages

    from addresses.selectors import AddressSelector
    from core.selectors import SchoolSelector

    school = SchoolSelector().get_current_school()
    if not school:
        messages.error(request, "Escola nao encontrada no tenant ativo.")
        return redirect("dashboard")

    addresses = AddressSelector().get_by_entity("school", school.pk)
    return render(
        request,
        "core/school_detail.html",
        {"school": school, "addresses": addresses},
    )


@login_required
def school_edit(request: HttpRequest) -> HttpResponse:
    """Tela de edicao dos dados da empresa (escola)."""
    from django.contrib import messages

    from addresses.selectors import AddressSelector
    from base.exceptions import BusinessRuleViolationError, ValidationError
    from core.forms import SchoolEditForm
    from core.selectors import SchoolSelector
    from core.services import SchoolService

    school = SchoolSelector().get_current_school()
    if not school:
        messages.error(request, "Escola nao encontrada no tenant ativo.")
        return redirect("dashboard")

    addresses = AddressSelector().get_by_entity("school", school.pk)

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

                messages.success(request, "Dados da empresa atualizados com sucesso.")
                return redirect("school_detail")
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

    return render(
        request,
        "core/school_edit.html",
        {"form": form, "school": school, "addresses": addresses},
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
