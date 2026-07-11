"""Testes do /health/ expandido e do /metrics/ com django-prometheus."""

import pytest


@pytest.mark.django_db
def test_health_returns_public_liveness_without_internal_checks(client):
    """Liveness pública não deve expor dependências internas."""
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_metrics_protected_when_not_debug(client, settings):
    """Em produção (DEBUG=False), /metrics/ exige staff — anon recebe 403."""
    settings.DEBUG = False
    response = client.get("/metrics/")
    assert response.status_code == 403
