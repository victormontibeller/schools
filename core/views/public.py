"""Landing page, probes operacionais e páginas de erro."""

import json
import logging

from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
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


def web_app_manifest(request: HttpRequest) -> JsonResponse:
    """Retorna o manifesto instalável sem qualquer dado do tenant ou usuário."""
    return JsonResponse(
        {
            "name": "School Manager",
            "short_name": "Schools",
            "start_url": "/app/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#3454d1",
            "icons": [
                {
                    "src": "/static/icons/school-manager.svg",
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any maskable",
                }
            ],
        },
        content_type="application/manifest+json",
    )


def service_worker(request: HttpRequest) -> FileResponse:
    """Entrega o worker na raiz para permitir escopo PWA sobre a aplicação."""
    from django.contrib.staticfiles import finders

    path = finders.find("js/service-worker.js")
    if not path:
        return HttpResponse(status=404)
    response = FileResponse(open(path, "rb"), content_type="application/javascript")  # noqa: SIM115
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def offline(request: HttpRequest) -> HttpResponse:
    """Exibe fallback público e genérico, sem dados autenticados em cache."""
    return render(request, "offline.html")


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
