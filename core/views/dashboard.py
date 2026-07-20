"""Dashboard principal do tenant."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render


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
            {"label": "Revisar agendas", "url": "diary_daily", "icon": "feather-check-square"},
            {"label": "Novo aluno", "url": "student_create", "icon": "feather-user-plus"},
            {"label": "Novo professor", "url": "teacher_create", "icon": "feather-user-check"},
            {"label": "Nova turma", "url": "class_create", "icon": "feather-layers"},
            {"label": "Usuários", "url": "users_list", "icon": "feather-users"},
        ],
        "COORDINATOR": [
            {"label": "Revisar agendas", "url": "diary_daily", "icon": "feather-check-square"},
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
            {"label": "Agenda", "url": "diary_daily", "icon": "feather-book-open"},
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

    from core.permissions import VIEW, can_access
    from dashboard.services import DashboardService

    role_name = _detect_dashboard_role(request.user)
    data = DashboardService(user=request.user).get_school_dashboard_data()
    diary_kpis = data.get("diary_kpis") or {}
    can_view_financial = can_access(request.user, "finance_overview", VIEW)
    can_view_revenue = can_access(request.user, "finance_revenue_reports", VIEW)
    can_view_overdue = can_access(request.user, "finance_overdue_reports", VIEW)
    return render(
        request,
        "dashboard.html",
        {
            "data": data,
            "quick_actions": _dashboard_quick_actions(role_name),
            "role_name": _dashboard_role_label(request.user, role_name),
            "greeting": _dashboard_greeting(),
            "can_view_financial": can_view_financial,
            "can_view_revenue": can_view_revenue,
            "can_view_overdue": can_view_overdue,
            "has_visible_attention": bool(
                data["students_at_risk"]
                or data["pending_activities"]
                or diary_kpis.get("pending_review")
                or diary_kpis.get("changes_requested")
                or (can_view_overdue and data["financial_kpis"]["total_vencido"])
            ),
        },
    )
