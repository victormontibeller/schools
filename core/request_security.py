"""Fronteiras HTTP: disponibilidade, tenant e observabilidade sem credenciais."""

import logging
from collections.abc import Callable
from typing import NoReturn

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotAllowed
from django_tenants.middleware.main import TenantMainMiddleware
from opentelemetry import trace


class ActiveTenantMiddleware(TenantMainMiddleware):
    """Recusa escolas desativadas antes de ativar o schema e a sessão."""

    def get_tenant(self, domain_model: type, hostname: str) -> object:
        """Resolve somente catálogo público ou escola disponível."""
        tenant = super().get_tenant(domain_model, hostname)
        if tenant.schema_name != "public" and (not tenant.is_active or tenant.deleted_at):
            raise Http404
        return tenant

    def no_tenant_found(self, request: HttpRequest, hostname: str) -> NoReturn:
        """Evita incluir o host informado pelo cliente na exceção."""
        raise Http404


class LivenessMiddleware:
    """Sonda exata independente de banco, host e sessão."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Responde apenas à URL pública de liveness."""
        if request.path_info == "/health/":
            if request.method not in {"GET", "HEAD"}:
                return HttpResponseNotAllowed(["GET", "HEAD"])
            from core.views.public import health

            response = health(request)
            if request.method == "HEAD":
                response.content = b""
            return response
        return self.get_response(request)


class SafeHttpLogFilter(logging.Filter):
    """Remove conteúdo não confiável de mensagens e exceções HTTP do framework."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Mantém status, rota canônica e tipo de erro, nunca URLs ou mensagens brutas."""
        if record.name.startswith("axes"):
            original = str(record.msg).lower()
            record.event_type = next(
                (
                    event
                    for text, event in (
                        ("successful login", "login_succeeded"),
                        ("login failed", "login_failed"),
                        ("locking", "login_locked"),
                        ("logout", "logout"),
                    )
                    if text in original
                ),
                "control",
            )
            record.route = (
                "logout"
                if "logout" in original
                else "login" if "login" in original else "unresolved"
            )
            record.msg = "authentication_control_event"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
            for key in (
                "username",
                "ip_address",
                "user_agent",
                "path_info",
                "credentials",
                "request",
                "message",
            ):
                record.__dict__.pop(key, None)
        if record.name.startswith(("django.request", "django.security", "django.server")):
            request = getattr(record, "request", None)
            record.route = getattr(
                getattr(request, "resolver_match", None), "view_name", "unresolved"
            )
            record.exception_type = record.exc_info[0].__name__ if record.exc_info else ""
            record.msg = "http_request_completed"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
            for field in (
                "request",
                "message",
                "path",
                "url",
                "referer",
                "status_message",
                "server_time",
            ):
                record.__dict__.pop(field, None)
        return True


class HttpTracingMiddleware:
    """Cria spans HTTP seguros sem instrumentação automática de URLs/exceções."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.tracer = trace.get_tracer(__name__)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Exporta somente método conhecido, rota resolvida e status numérico."""
        with self.tracer.start_as_current_span(
            "http.request",
            kind=trace.SpanKind.SERVER,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            response = self.get_response(request)
            route = getattr(getattr(request, "resolver_match", None), "view_name", "unresolved")
            span.update_name(route)
            span.set_attribute("http.route", route)
            span.set_attribute("http.response.status_code", response.status_code)
            if request.method in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
                span.set_attribute("http.request.method", request.method)
            return response
