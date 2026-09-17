"""Entrega local de mídia pública sem expor arquivos privados."""

from importlib import reload

import pytest
from django.core.files.storage import storages
from django.test import override_settings
from django.urls import Resolver404, clear_url_caches, resolve

from base.tests.images import png_upload


@pytest.fixture()
def public_media_urls(tmp_path):
    import core.urls

    try:
        with override_settings(
            DEBUG=True,
            STORAGES={
                "public": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage",
                    "OPTIONS": {"location": tmp_path / "public", "base_url": "/media/"},
                },
            },
        ):
            reload(core.urls)
            clear_url_caches()
            yield tmp_path
    finally:
        reload(core.urls)
        clear_url_caches()


@pytest.mark.django_db
@pytest.mark.parametrize("authenticated", [False, True])
def test_get_public_logo_returns_image(client, user, public_media_urls, authenticated):
    if authenticated:
        client.force_login(user)
    upload = png_upload()
    expected = upload.read()
    upload.seek(0)
    storage = storages["public"]
    name = storage.save("demo/logos/schools/logo.png", upload)

    response = client.get(storage.url(name))

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert b"".join(response.streaming_content) == expected


@pytest.mark.django_db
def test_get_public_media_cannot_read_private_files(client, user, public_media_urls):
    client.force_login(user)
    private = public_media_urls / "private"
    private.mkdir()
    (private / "secret.png").write_bytes(b"private-content")
    for path in ("secret.png", "private/secret.png", "../private/secret.png"):
        response = client.get("/media/" + path)
        assert response.status_code in {400, 404}
        assert b"private-content" not in response.content


def test_get_public_media_route_is_absent_in_production():
    import core.urls

    try:
        with override_settings(DEBUG=False):
            reload(core.urls)
            clear_url_caches()
            with pytest.raises(Resolver404):
                resolve("/media/demo/logos/schools/logo.png")
    finally:
        reload(core.urls)
        clear_url_caches()
