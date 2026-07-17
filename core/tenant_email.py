"""Resolve o remetente Resend do tenant atual sem fallback entre escolas."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_tenant_resend_config() -> dict[str, object]:
    """Retorna a configuração Resend do tenant atual sem aplicar fallback entre escolas."""
    try:
        from django.db import connection
        from django_tenants.utils import get_tenant_model

        schema = getattr(connection, "schema_name", "public")
        tenant = get_tenant_model().objects.filter(schema_name=schema).first()
        email_config = dict((tenant.settings or {}).get("email", {})) if tenant else {}
        return {
            "from_email": str(email_config.get("from_email", "")).strip(),
            "domain": str(email_config.get("resend_domain", "")).strip().lower(),
            "verified": bool(email_config.get("resend_verified", False)),
            "school_name": tenant.name if tenant else "",
        }
    except Exception as exc:
        logger.debug(
            "tenant_resend_config_unavailable",
            extra={"exception_type": type(exc).__name__},
        )
        return {"from_email": "", "domain": "", "verified": False, "school_name": ""}
