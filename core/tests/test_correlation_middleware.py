"""Testes da normalização HTTP do correlation ID."""

import uuid

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from base import context
from core.middleware import CorrelationIdMiddleware


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("550E8400-E29B-41D4-A716-446655440000", "550e8400-e29b-41d4-a716-446655440000"),
        ("not-a-uuid", None),
        ("x" * 100, None),
        ("550e8400-e29b-41d4-a716-446655440000\x7f", None),
    ],
)
def test_correlation_middleware_uses_same_sanitized_value_in_context_and_response(header, expected):
    """O header bruto nunca alcança o contexto nem a resposta."""
    observed = []

    def response(request):
        observed.append(context.correlation_id.get())
        return HttpResponse()

    request = RequestFactory().get("/", HTTP_X_CORRELATION_ID=header)
    result = CorrelationIdMiddleware(response)(request)

    sanitized = result["X-Correlation-ID"]
    assert observed == [sanitized]
    assert sanitized == expected if expected else sanitized != header
    assert str(uuid.UUID(sanitized)) == sanitized
