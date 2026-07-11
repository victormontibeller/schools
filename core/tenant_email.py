"""Resolvedor de configuracao de e-mail por tenant.

Cada escola (tenant) pode definir seu proprio remetente via
`School.settings["email"]`. O fallback usa as variaveis globais do .env
(usado para o schema `public` e emails de sistema).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_tenant_from_email() -> str:
    """Retorna o e-mail do remetente para o tenant atual.

    Resolucao:
        1. `School.settings["email"]["from_email"]` — especifico do tenant.
        2. `DEFAULT_FROM_EMAIL` do .env — fallback global.

    Em tarefas Celery sem contexto de tenant, retorna o fallback global.
    """
    from django.conf import settings

    try:
        from django_tenants.utils import get_tenant_model

        tenant = get_tenant_model().objects.filter(schema_name="public").first()
        # Tenta obter o tenant atual via middleware django-tenants.
        from django.db import connection

        schema = connection.schema_name
        if schema and schema != "public":
            tenant = get_tenant_model().objects.filter(schema_name=schema).first()

        if tenant and tenant.settings:
            tenant_email = tenant.settings.get("email", {})
            from_email = tenant_email.get("from_email", "").strip()
            if from_email:
                return from_email
    except Exception:
        logger.debug("tenant_email_fallback", exc_info=True)

    return settings.DEFAULT_FROM_EMAIL


def get_tenant_email_display() -> str:
    """Retorna nome + e-mail formatado para o header From (ex: 'Escola ABC <abc@escola.com>')."""
    from django.conf import settings

    try:
        from django.db import connection
        from django_tenants.utils import get_tenant_model

        schema = connection.schema_name
        tenant_model = get_tenant_model()
        tenant = tenant_model.objects.filter(schema_name=schema).first()

        if tenant:
            name = tenant.name
            email_config = (tenant.settings or {}).get("email", {})
            address = email_config.get("from_email", "").strip() or settings.DEFAULT_FROM_EMAIL
            return f"{name} <{address}>"
    except Exception:
        logger.debug("tenant_email_display_fallback", exc_info=True)

    return settings.DEFAULT_FROM_EMAIL
