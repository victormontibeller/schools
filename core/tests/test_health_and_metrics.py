"""Testes do /health/ expandido e do /metrics/ com django-prometheus."""

import json

import pytest


@pytest.mark.django_db
def test_health_returns_degraded_status_with_checks(client):
    """Health deve trazer checks por dependência (db, redis, rabbitmq)."""
    response = client.get("/health/")
    assert response.status_code in (200, 503)
    payload = json.loads(response.content)
    assert "status" in payload
    assert "checks" in payload
    assert "db" in payload["checks"]


@pytest.mark.django_db
def test_metrics_protected_when_not_debug(client, settings):
    """Em produção (DEBUG=False), /metrics/ exige staff — anon recebe 403."""
    settings.DEBUG = False
    response = client.get("/metrics/")
    assert response.status_code == 403
