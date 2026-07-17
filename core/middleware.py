"""Middlewares: Correlation ID, Audit Context e Handler global de exceções."""

import json
import logging
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from base import context
from base.exceptions import (
    AppBaseError,
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    TenantNotFoundError,
    ValidationError,
)


class CorrelationIdFilter(logging.Filter):
    """Injeta identificadores operacionais seguros em cada log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Preenche o contexto sem sobrescrever extras definidos pelo chamador."""
        values = {
            "correlation_id": context.correlation_id.get() or "-",
            "tenant": context.current_tenant.get() or "-",
            "user_id": context.user_id.get() or "-",
        }
        for key, value in values.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class TenantContextMiddleware:
    """Sincroniza o schema resolvido pelo django-tenants com contextvars."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Mantém o tenant correto durante todo o ciclo da requisição."""
        from django.db import connection

        tenant = getattr(request, "tenant", None)
        schema = getattr(tenant, "schema_name", None) or getattr(
            connection, "schema_name", "public"
        )
        token = context.current_tenant.set(schema)
        try:
            return self.get_response(request)
        finally:
            context.current_tenant.reset(token)


class SecurityHeadersMiddleware:
    """Aplica CSP e cabeçalhos complementares em todas as respostas."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Adiciona política restritiva compatível com os assets atuais."""
        response = self.get_response(request)
        response.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'",
        )
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response


class HtmxBoostMiddleware:
    """Diferencia navegacao boosted de requisicoes HTMX de componentes."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Faz views renderizarem o documento completo em navegacao boosted."""
        if request.META.get("HTTP_HX_BOOSTED", "").lower() == "true":
            request.is_htmx_boosted = True
            request.META.pop("HTTP_HX_REQUEST", None)
            request.__dict__.pop("headers", None)
        return self.get_response(request)


class CorrelationIdMiddleware:
    """Gera/lê X-Correlation-ID e armazena em context var."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Define o correlation_id no contexto e o devolve no response."""
        cid = request.META.get("HTTP_X_CORRELATION_ID", "").strip() or str(uuid.uuid4())
        token = context.correlation_id.set(cid)
        try:
            response = self.get_response(request)
        finally:
            context.correlation_id.reset(token)
        response["X-Correlation-ID"] = cid
        return response


class AuditContextMiddleware:
    """Captura IP e User-Agent para enriquecimento de auditoria."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Captura IP, User-Agent e usuário no contexto de auditoria."""
        ip = self._get_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")[:512]
        user = getattr(request, "user", None)
        uid = user.pk if user and user.is_authenticated else None

        tokens = (
            context.request_ip.set(ip),
            context.user_agent.set(ua),
            context.user_id.set(uid),
        )
        try:
            response = self.get_response(request)
        finally:
            context.request_ip.reset(tokens[0])
            context.user_agent.reset(tokens[1])
            context.user_id.reset(tokens[2])
        return response

    @staticmethod
    def _get_ip(request: HttpRequest) -> str:
        from django.conf import settings

        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        remote = request.META.get("REMOTE_ADDR", "")
        trusted = set(getattr(settings, "TRUSTED_PROXY_IPS", []))
        return xff.split(",")[0].strip() if xff and remote in trusted else remote


class PermissionPolicyMiddleware(MiddlewareMixin):
    """Aplica RBAC de módulo antes da execução das views autenticadas."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Bloqueia módulos e ações incompatíveis com o papel corrente."""
        from django.core.exceptions import PermissionDenied

        from core.permissions import (
            GUARDIAN_VIEW_NAMES,
            PUBLIC_VIEW_NAMES,
            SELF_SERVICE_VIEW_NAMES,
            can_access,
            has_unrestricted_tenant_access,
            resolve_view_access,
        )

        view_name = getattr(request.resolver_match, "url_name", "")
        if view_name in PUBLIC_VIEW_NAMES or not request.user.is_authenticated:
            return None
        current_role = getattr(getattr(request.user, "role", None), "name", "")
        if view_name in SELF_SERVICE_VIEW_NAMES or (
            view_name == "justification_create" and current_role == "GUARDIAN"
        ):
            return None
        module_key, action = resolve_view_access(
            view_func,
            view_name,
            request.method,
            view_kwargs,
        )
        if (
            getattr(request.user, "access_mode", "") == "DEMO"
            and not has_unrestricted_tenant_access(request.user)
            and module_key
            not in {
                "schedule",
                "activities",
                "attendance",
                "classes",
                "enrollments",
                "dashboard",
                "student_diary",
                "diary_configuration",
            }
        ):
            raise PermissionDenied("Ação indisponível no ambiente DEMO.")
        if current_role == "GUARDIAN":
            if view_name not in GUARDIAN_VIEW_NAMES:
                raise PermissionDenied("Sem permissão para esta operação.")
            from core.access_selectors import ObjectAccessSelector

            student_id = view_kwargs.get("student_id")
            if view_name == "student_profile":
                student_id = view_kwargs.get("pk")
            if student_id and not ObjectAccessSelector.guardian_can_access_student(
                request.user.pk, student_id
            ):
                raise PermissionDenied("Aluno não vinculado a este responsável.")
            if (
                view_name == "activity_detail"
                and not ObjectAccessSelector.guardian_can_access_activity(
                    request.user.pk, view_kwargs.get("pk")
                )
            ):
                raise PermissionDenied("Atividade fora do escopo do responsável.")
            if not can_access(request.user, module_key or "", action):
                raise PermissionDenied("Sem permissão para esta operação.")
            return None
        if current_role == "TEACHER":
            from core.access_selectors import ObjectAccessSelector

            class_id = view_kwargs.get("class_id")
            if view_name in {"class_detail", "class_edit"}:
                class_id = view_kwargs.get("pk")
            if class_id and not ObjectAccessSelector.teacher_can_access_class(
                request.user.pk, class_id
            ):
                raise PermissionDenied("Turma fora do escopo do professor.")
            if (
                view_name == "teacher_schedule"
                and not ObjectAccessSelector.teacher_can_access_teacher(
                    request.user.pk, view_kwargs.get("teacher_id")
                )
            ):
                raise PermissionDenied("Grade fora do escopo do professor.")
            if view_name in {
                "activity_detail",
                "activity_edit",
                "activity_record_score",
                "activity_group_create",
                "activity_group_edit",
                "activity_group_apply_result",
                "activity_group_deactivate",
            }:
                if not ObjectAccessSelector.teacher_can_access_activity(
                    request.user.pk, view_kwargs.get("pk")
                ):
                    raise PermissionDenied("Atividade fora do escopo do professor.")
            if view_name in {"subject_detail", "subject_edit", "subject_deactivate"}:
                if not ObjectAccessSelector.teacher_can_access_subject(
                    request.user.pk, view_kwargs.get("pk")
                ):
                    raise PermissionDenied("Disciplina fora do escopo do professor.")
            if (
                view_name == "attendance_record_fill"
                and not ObjectAccessSelector.teacher_can_access_attendance(
                    request.user.pk, view_kwargs.get("record_id")
                )
            ):
                raise PermissionDenied("Chamada fora do escopo do professor.")
            student_id = view_kwargs.get("student_id")
            if student_id and not ObjectAccessSelector.teacher_can_access_student(
                request.user.pk, student_id
            ):
                raise PermissionDenied("Aluno fora do escopo do professor.")
        if not module_key or not can_access(request.user, module_key, action):
            raise PermissionDenied("Sem permissão para esta operação.")
        return None


# ── Handler global de exceções HTTP ──────────────────────────────────────────


_LOG = logging.getLogger(__name__)

# Mapeamento exceção da aplicação → (código, status HTTP).
_EXCEPTION_MAP: dict[type[AppBaseError], tuple[str, int]] = {
    ValidationError: ("validation_error", 400),
    ObjectNotFoundError: ("not_found", 404),
    TenantNotFoundError: ("tenant_not_found", 404),
    PermissionDeniedError: ("permission_denied", 403),
    BusinessRuleViolationError: ("business_rule_violation", 422),
}


class ExceptionHandlerMiddleware:
    """Converte exceções de domínio (`AppBaseError`) em respostas HTTP padronizadas.

    Garante que erros de validação, registros não encontrados, violações de regra
    de negócio e bloqueios de permissão nunca cheguem ao handler 500 genérico.
    Responde em JSON para requisições que aceitam JSON; caso contrário, renderiza
    o template `errors/business.html` com a mensagem amigável.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Armazena o próximo handler da cadeia de middlewares."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Executa o handler e captura exceções de domínio, se houver."""
        try:
            return self.get_response(request)
        except AppBaseError as exc:
            return self._build_response(request, exc)

    def process_exception(self, request: HttpRequest, exception: Exception):
        """Captura exceções de domínio no caminho `process_exception` do Django.

        Necessário porque o Django consome exceções de view internamente antes
        que elas cheguem ao `__call__` do middleware.
        """
        if isinstance(exception, AppBaseError):
            return self._build_response(request, exception)
        return None

    @staticmethod
    def _build_response(request: HttpRequest, exc: AppBaseError) -> HttpResponse:
        """Produz a resposta HTTP a partir da exceção capturada."""
        code, status = _EXCEPTION_MAP.get(type(exc), ("app_error", 500))
        cid = context.correlation_id.get() or "-"
        _LOG.warning(
            "Exceção de domínio capturada",
            extra={
                "correlation_id": cid,
                "exception_type": type(exc).__name__,
                "status_code": status,
                "path": request.path,
                "method": request.method,
            },
        )
        body = {"error": code, "message": exc.message, "correlation_id": cid}
        if isinstance(exc, ValidationError) and exc.errors:
            body["errors"] = exc.errors

        accept = request.META.get("HTTP_ACCEPT", "")
        wants_json = "application/json" in accept
        if request.headers.get("HX-Request") or wants_json:
            return HttpResponse(
                content=json.dumps(body, ensure_ascii=False),
                content_type="application/json",
                status=status,
            )
        from django.shortcuts import render

        return render(
            request,
            "errors/business.html",
            {"code": code, "message": exc.message, "correlation_id": cid, "status": status},
            status=status,
        )
