"""Cabeçalhos seguros também em respostas anteriores à resolução do tenant."""

import pytest
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import reverse

from core.middleware import SecurityHeadersMiddleware


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path,status,policy,no_store",
    [
        ("/convite-professor/synthetic-secret/?token=synthetic-secret", 404, "strict-origin", True),
        ("/convite-responsavel/?token=synthetic-secret", 500, "strict-origin", True),
        ("/convite-responsavel/?token=synthetic-secret", 304, "strict-origin", True),
        ("/unknown/synthetic-secret/?token=synthetic-secret", 404, "strict-origin", True),
        ("/unknown/synthetic-secret/", 301, "strict-origin", True),
        ("/login/", 302, "same-origin", False),
        ("/login/", 200, "same-origin", False),
    ],
)
def test_early_response_protects_token_routes_without_database_access(
    django_assert_num_queries, path, status, policy, no_store
):
    middleware = SecurityHeadersMiddleware(lambda request: HttpResponse(status=status))
    request = RequestFactory().get(path)
    with django_assert_num_queries(0):
        response = middleware(request)
    assert response["Referrer-Policy"] == policy
    assert (response.get("Cache-Control") == "no-store") is no_store


def test_static_response_preserves_immutable_cache():
    response = HttpResponse(headers={"Cache-Control": "max-age=315360000, public, immutable"})
    middleware = SecurityHeadersMiddleware(lambda request: response)
    result = middleware(RequestFactory().get("/static/css/school-manager.abcdef.css"))
    assert result["Cache-Control"] == "max-age=315360000, public, immutable"
    assert result["Referrer-Policy"] == "same-origin"


@pytest.mark.django_db
def test_token_post_still_requires_csrf():
    response = Client(enforce_csrf_checks=True).post(
        reverse("guardian_invitation") + "?token=synthetic-secret",
        {"password": "CoralHorizon842", "password_confirm": "CoralHorizon842"},
        HTTP_ORIGIN="http://testserver",
    )
    assert response.status_code == 403
    assert response["Referrer-Policy"] == "strict-origin"
    assert response["Cache-Control"] == "no-store"
