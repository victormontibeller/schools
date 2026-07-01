"""Testes do middleware de tratamento global de exceções."""

import json

import pytest

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from core.middleware import ExceptionHandlerMiddleware


def _mw(get_response):
    """Constrói o middleware com um handler qualquer."""
    return ExceptionHandlerMiddleware(get_response)


@pytest.mark.django_db
def test_validation_error_returns_400_json(client):
    """Uma ValidationError levantada deve virar 400 JSON para clientes que aceitam JSON."""

    def raising_view(request):
        raise ValidationError("ruim", errors={"x": ["obrigatório"]})

    from django.test import RequestFactory

    rf = RequestFactory()
    request = rf.get("/", HTTP_ACCEPT="application/json")

    response = _mw(raising_view)(request)
    assert response.status_code == 400
    payload = json.loads(response.content)
    assert payload["error"] == "validation_error"
    assert payload["errors"] == {"x": ["obrigatório"]}


@pytest.mark.django_db
def test_object_not_found_returns_404():
    """ObjectNotFoundError deve mapear para 404."""

    from django.test import RequestFactory

    rf = RequestFactory()

    def view(request):
        raise ObjectNotFoundError("Student", "abc")

    response = _mw(view)(rf.get("/", HTTP_ACCEPT="application/json"))
    assert response.status_code == 404
    assert json.loads(response.content)["error"] == "not_found"


@pytest.mark.django_db
def test_business_rule_violation_returns_422():
    """BusinessRuleViolationError deve mapear para 422."""

    from django.test import RequestFactory

    rf = RequestFactory()

    def view(request):
        raise BusinessRuleViolationError("sem vagas")

    response = _mw(view)(rf.get("/", HTTP_ACCEPT="application/json"))
    assert response.status_code == 422
    assert json.loads(response.content)["message"] == "sem vagas"


@pytest.mark.django_db
def test_permission_denied_returns_403():
    """PermissionDeniedError deve mapear para 403."""

    from django.test import RequestFactory

    rf = RequestFactory()

    def view(request):
        raise PermissionDeniedError()

    response = _mw(view)(rf.get("/", HTTP_ACCEPT="application/json"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_html_request_renders_business_template(client, django_user_model):
    """Requisições que não aceitam JSON devem renderizar errors/business.html."""

    from django.test import RequestFactory

    rf = RequestFactory()

    def view(request):
        raise ValidationError("inválido")

    response = _mw(view)(rf.get("/"))
    assert response.status_code == 400
    assert "inválido".encode() in response.content
