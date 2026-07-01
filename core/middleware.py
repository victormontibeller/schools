"""Middlewares: Correlation ID, Audit Context e Handler global de exceções."""

import json
import logging
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

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
    """Injeta correlation_id em cada log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Injeta o correlation_id corrente no record de log."""
        record.correlation_id = context.correlation_id.get() or "-"
        return True


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
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")


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
