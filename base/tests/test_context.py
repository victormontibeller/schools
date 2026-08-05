"""Testes dos contratos explícitos de schema escolar."""

import pytest

from base import context
from base.exceptions import BusinessRuleViolationError


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
