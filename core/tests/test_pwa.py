"""Testes da camada instalável e do cache público seguro."""

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse


@pytest.mark.django_db
def test_manifest_and_service_worker_are_public(client):
    manifest = client.get(reverse("web_app_manifest"))
    worker = client.get(reverse("service_worker"))

    assert manifest.status_code == 200
    assert manifest.json()["display"] == "standalone"
    assert worker.status_code == 200
    assert worker["Service-Worker-Allowed"] == "/"


@pytest.mark.django_db
def test_service_worker_does_not_cache_authenticated_routes(client):
    response = client.get(reverse("service_worker"))
    content = b"".join(response.streaming_content).decode()

    assert 'url.pathname.startsWith("/static/")' in content
    assert "caches.open" in content
    assert '"/app/"' not in content.split("const SHELL", 1)[1].split("];", 1)[0]
    assert 'addEventListener("push"' not in content
    assert "showNotification" not in content


def test_pwa_script_only_registers_service_worker():
    path = finders.find("js/pwa.js")
    with open(path, encoding="utf-8") as script:
        content = script.read()

    assert 'register("/service-worker.js")' in content
    assert "PushManager" not in content
    assert "requestPermission" not in content
