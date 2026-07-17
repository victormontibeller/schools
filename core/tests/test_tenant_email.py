"""Testes do resolvedor de remetente Resend por tenant."""

import pytest


@pytest.mark.django_db
def test_get_tenant_resend_config_does_not_fallback_between_schools(user, monkeypatch):
    from django.db import connection

    from core.tenant_email import get_tenant_resend_config
    from tenancy.models import School

    monkeypatch.setattr(connection, "schema_name", "demo", raising=False)
    School.objects.create(
        schema_name="demo",
        name="Escola Demo",
        settings={
            "email": {
                "from_email": "agenda@mail.example.com",
                "resend_domain": "MAIL.EXAMPLE.COM",
                "resend_verified": True,
            }
        },
        created_by=user,
        updated_by=user,
    )

    assert get_tenant_resend_config() == {
        "from_email": "agenda@mail.example.com",
        "domain": "mail.example.com",
        "verified": True,
        "school_name": "Escola Demo",
    }


@pytest.mark.django_db
def test_get_tenant_resend_config_returns_empty_when_tenant_is_missing(monkeypatch):
    from django.db import connection

    from core.tenant_email import get_tenant_resend_config

    monkeypatch.setattr(connection, "schema_name", "missing", raising=False)
    assert get_tenant_resend_config() == {
        "from_email": "",
        "domain": "",
        "verified": False,
        "school_name": "",
    }
