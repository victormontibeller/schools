"""Validação central de hosts gerenciados pela plataforma."""

from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError

_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def normalize_domain(value: str, *, tenant_schema: str | None = None) -> str:
    """Normaliza um host e restringe produção aos domínios administrados."""
    host = (value or "").strip().lower().rstrip(".")
    if "://" in host or "/" in host or ":" in host or not _HOST_RE.fullmatch(host):
        raise ValidationError("Informe um host válido, sem protocolo, porta ou caminho.")

    if settings.DJANGO_ENV != "production":
        return host

    if tenant_schema == "public":
        if host != settings.PLATFORM_DOMAIN:
            raise ValidationError("O schema público deve usar o domínio da plataforma.")
        return host

    suffix = f".{settings.TENANT_BASE_DOMAIN}"
    subdomain = host.removesuffix(suffix)
    if not host.endswith(suffix) or not subdomain or "." in subdomain:
        raise ValidationError("O domínio deve ser um subdomínio gerenciado pela plataforma.")
    return host
