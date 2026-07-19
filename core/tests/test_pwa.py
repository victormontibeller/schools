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


@pytest.mark.django_db
def test_service_worker_refreshes_custom_css_before_using_cache(client):
    response = client.get(reverse("service_worker"))
    content = b"".join(response.streaming_content).decode()
    shell = content.split("const SHELL", 1)[1].split("];", 1)[0]

    assert 'CACHE_NAME = "schools-shell-v3"' in content
    assert "school-manager.css" not in shell
    assert "school-manager(?:\\.[0-9a-f]{12})?\\.css" in content
    assert 'fetch(event.request, {cache: "no-store"})' in content
    assert "cache.put(event.request, response.clone())" in content


def test_pwa_script_registers_worker_and_refreshes_existing_clients():
    path = finders.find("js/pwa.js")
    with open(path, encoding="utf-8") as script:
        content = script.read()

    assert 'register("/service-worker.js")' in content
    assert 'addEventListener("controllerchange"' in content
    assert "hadController && !refreshing" in content
    assert "PushManager" not in content
    assert "requestPermission" not in content
