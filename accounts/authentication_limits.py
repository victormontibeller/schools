"""Limites compartilhados para recuperação e convites; nenhuma identidade em cache."""

from django.core.cache import caches
from django.http import HttpResponse
from django.utils.crypto import salted_hmac
from django.utils.deprecation import MiddlewareMixin

from base.context import current_tenant


class AuthenticationLimit:
    """Contadores atômicos com expiração; indisponibilidade recusa novas tentativas."""

    @staticmethod
    def reserve(*, scope, ip, recipient="", limit=10, recipient_limit=3, seconds=3600):
        cache = caches["authentication"]
        dimensions = [("ip", ip, limit)]
        if recipient:
            dimensions.append(("identity", recipient.strip().casefold(), recipient_limit))
        try:
            allowed = True
            for dimension, value, maximum in dimensions:
                digest = salted_hmac(
                    "schools.authentication-limit.v1",
                    f"{current_tenant.get()}|{scope}|{dimension}|{value}",
                    algorithm="sha256",
                ).hexdigest()
                key = f"access-limit:{digest}"
                count = 1 if cache.add(key, 1, timeout=seconds) else cache.incr(key)
                allowed = allowed and count <= maximum
            return (True, 0) if allowed else (False, 429)
        except Exception:
            # Redis outages must never turn an authentication endpoint into an unlimited sender.
            return False, 503


class AuthenticationLimitMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != "POST":
            return None
        name = getattr(request.resolver_match, "url_name", "")
        if name == "password_reset":
            kwargs = {"scope": "reset-request", "recipient": request.POST.get("email", "")}
            seconds = 3600
        elif name in {
            "password_reset_confirm",
            "staff_invitation",
            "guardian_invitation",
            "teacher_invitation",
        }:
            kwargs = {"scope": "access-confirmation", "limit": 30}
            seconds = 900
        elif name in {"staff_user_invite", "guardian_invite", "teacher_invite"}:
            kwargs = {
                "scope": "invitation-send",
                "recipient": str(view_kwargs.get("pk", "")),
                "limit": 20,
                "recipient_limit": 3,
            }
            seconds = 3600
        else:
            return None
        from core.middleware import AuditContextMiddleware

        allowed, status = AuthenticationLimit.reserve(
            ip=AuditContextMiddleware._get_ip(request), seconds=seconds, **kwargs
        )
        if allowed:
            return None
        response = HttpResponse(
            "Não foi possível processar a solicitação agora. Aguarde e tente novamente. "
            "Se precisar de ajuda imediata, entre em contato com a escola.",
            status=status,
            content_type="text/plain; charset=utf-8",
        )
        response["Retry-After"] = str(seconds if status == 429 else 60)
        response["Cache-Control"] = "no-store"
        return response
