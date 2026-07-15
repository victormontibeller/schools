"""Testes da política de domínios gerenciados."""

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings

from tenancy.domain_validation import normalize_domain


def test_normalize_domain_removes_case_spaces_and_trailing_dot():
    assert normalize_domain(" Escola.LOCALHOST. ") == "escola.localhost"


@pytest.mark.parametrize(
    "value",
    ["https://escola.example.com", "escola.example.com/path", "escola.example.com:443"],
)
def test_normalize_domain_rejects_url_components(value):
    with pytest.raises(ValidationError):
        normalize_domain(value)


@override_settings(
    DJANGO_ENV="production",
    PLATFORM_DOMAIN="platform.example.com",
    TENANT_BASE_DOMAIN="schools.example.com",
)
def test_normalize_domain_accepts_managed_tenant_subdomain():
    assert (
        normalize_domain("colegio.schools.example.com", tenant_schema="colegio")
        == "colegio.schools.example.com"
    )


@override_settings(
    DJANGO_ENV="production",
    PLATFORM_DOMAIN="platform.example.com",
    TENANT_BASE_DOMAIN="schools.example.com",
)
def test_normalize_domain_rejects_host_outside_managed_base():
    with pytest.raises(ValidationError):
        normalize_domain("colegio.attacker.invalid", tenant_schema="colegio")


@override_settings(
    DJANGO_ENV="production",
    PLATFORM_DOMAIN="platform.example.com",
    TENANT_BASE_DOMAIN="schools.example.com",
)
def test_normalize_domain_rejects_nested_subdomain():
    with pytest.raises(ValidationError):
        normalize_domain("unidade.colegio.schools.example.com", tenant_schema="colegio")
