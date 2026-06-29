"""Health check, landing page pública e dashboard principal."""

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

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
    """Endpoint de health check retornando JSON com status ok."""
    return HttpResponse(
        content=json.dumps({"status": "ok"}),
        content_type="application/json",
        status=200,
    )


def index(request: HttpRequest) -> HttpResponse:
    """Landing page pública de vendas do SaaS.

    Não exige login — apresenta a plataforma a escolas potenciais e os
    direciona para o login/assinatura. Usuários já autenticados são
    encaminhados direto ao dashboard.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

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
        {"name": "Professores", "url": "teachers_list", "icon": "feather-book-open"},
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
