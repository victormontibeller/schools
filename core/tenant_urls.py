"""URLs absolutas derivadas exclusivamente do domínio canônico da escola."""

from urllib.parse import urlsplit

from django.conf import settings

from base.exceptions import BusinessRuleViolationError


def school_url(school, path):
    parts = urlsplit(path)
    if parts.scheme or parts.netloc or not path.startswith("/") or path.startswith("//"):
        raise BusinessRuleViolationError("Informe somente uma rota interna da escola.")
    domain = school.domains.filter(is_primary=True).first()
    if not domain:
        raise BusinessRuleViolationError("A escola precisa de domínio principal.")
    host = domain.domain
    if settings.FICTITIOUS_MODE:
        from core.fictitious import require_fictitious

        require_fictitious(schema=school.schema_name)
        expected = (
            "platform.localhost"
            if school.schema_name == "public"
            else f"{school.schema_name.replace('_', '-')}.localhost"
        )
        if host != expected:
            raise BusinessRuleViolationError("Domínio fora do ensaio fictício autorizado.")
        host = f"{host}:{settings.FICTITIOUS_HTTP_PORT}"
    return f"{'http' if settings.DEBUG else 'https'}://{host}{path}"
