"""Barreira explícita do ensaio fictício local; nunca habilitada implicitamente."""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

TEMPORARY_ROOT = Path("/tmp").resolve()  # noqa: S108 -- allowlist; no shared file is created here
FICTITIOUS_SCHEMAS = frozenset({"public", "piloto", "piloto_comparacao"})


def validate_configuration(
    *,
    enabled,
    environment,
    debug,
    database,
    directory,
    media_root,
    port,
    platform_domain,
    base_domain,
):
    if not enabled:
        return
    root = Path(directory).resolve()
    media = Path(media_root).resolve()
    if (
        environment == "production"
        or not debug
        or database.get("HOST") not in {"localhost", "127.0.0.1", "::1"}
        or not str(database.get("NAME", "")).startswith("schools_pilot_")
        or not root.is_relative_to(TEMPORARY_ROOT)
        or root == TEMPORARY_ROOT
        or not media.is_relative_to(root)
        or platform_domain != "platform.localhost"
        or base_domain != "localhost"
        or not 1024 <= port <= 65535
    ):
        raise ImproperlyConfigured(
            "Configuração fictícia exige DEBUG, banco loopback e diretório privado temporário."
        )


def require_fictitious(*, schema=None, recipient=None):
    from django.conf import settings

    from base.context import current_tenant
    from base.exceptions import BusinessRuleViolationError

    if not settings.FICTITIOUS_MODE:
        raise BusinessRuleViolationError("Operação exclusiva do ambiente fictício local.")
    validate_configuration(
        enabled=True,
        environment=settings.DJANGO_ENV,
        debug=settings.DEBUG,
        database=settings.DATABASES["default"],
        directory=settings.FICTITIOUS_DIRECTORY,
        media_root=settings.MEDIA_ROOT,
        port=settings.FICTITIOUS_HTTP_PORT,
        platform_domain=settings.PLATFORM_DOMAIN,
        base_domain=settings.TENANT_BASE_DOMAIN,
    )
    if (schema or current_tenant.get()) not in FICTITIOUS_SCHEMAS:
        raise BusinessRuleViolationError("Schema fora do ensaio fictício autorizado.")
    if recipient is not None:
        domain = recipient.rpartition("@")[2].lower()
        if domain != "example.test" and not domain.endswith(".example.test"):
            raise BusinessRuleViolationError(
                "Transporte fictício aceita somente endereços reservados."
            )
    return Path(settings.FICTITIOUS_DIRECTORY).resolve()


def task_publication_enabled(schema):
    from django.conf import settings

    if not settings.FICTITIOUS_MODE:
        return True
    require_fictitious(schema=schema)
    return False
