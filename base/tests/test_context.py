"""Testes dos contratos explícitos de schema escolar."""

import uuid

import pytest

from base import context
from base.exceptions import BusinessRuleViolationError


def test_normalize_http_correlation_id_canonicalizes_valid_uuid() -> None:
    """UUID válido recebido em caixa alta usa a representação canônica."""
    value = "550E8400-E29B-41D4-A716-446655440000"

    assert context.normalize_http_correlation_id(value) == value.lower()


@pytest.mark.parametrize(
    "value",
    [None, "", "not-a-uuid", "x" * 37, "550e8400-e29b-41d4-a716-446655440000\n"],
)
def test_normalize_http_correlation_id_replaces_unsafe_input(value) -> None:
    """Entrada HTTP ausente ou insegura é substituída por UUID v4."""
    normalized = context.normalize_http_correlation_id(value)

    parsed = uuid.UUID(normalized)
    assert parsed.version == 4
    assert normalized != value


def test_require_tenant_schema_returns_active_schema_when_expected_matches() -> None:
    token = context.current_tenant.set("school_a")
    try:
        assert context.active_tenant_schema() == "school_a"
        assert context.require_tenant_schema("school_a") == "school_a"
    finally:
        context.current_tenant.reset(token)


@pytest.mark.parametrize(
    ("active", "expected"),
    [
        ("public", "school_a"),
        ("", "school_a"),
        ("school_a", "public"),
        ("school_a", ""),
        ("school_a", "school_b"),
    ],
)
def test_require_tenant_schema_rejects_missing_public_or_mismatched_schema(
    active, expected
) -> None:
    token = context.current_tenant.set(active)
    try:
        with pytest.raises(BusinessRuleViolationError):
            context.require_tenant_schema(expected)
    finally:
        context.current_tenant.reset(token)
