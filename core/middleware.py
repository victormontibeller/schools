"""Middlewares: Correlation ID e Audit Context."""

import logging
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from base import context


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
