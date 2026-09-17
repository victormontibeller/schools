"""Helpers de imagens válidas para testes de upload."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def png_upload(name: str = "avatar.png") -> SimpleUploadedFile:
    """Retorna um PNG 1x1 íntegro."""
    buffer = BytesIO()
    Image.new("RGB", (1, 1), color="white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def isolate_media_storages(settings, monkeypatch, tmp_path):
    """Redireciona também FileFields já materializados, sem tocar mídia real."""
    from django.apps import apps
    from django.core.files.storage import storages
    from django.db.models import FileField

    from base.media import get_public_storage

    settings.STORAGES = {
        **settings.STORAGES,
        "default": {
            "BACKEND": "base.media.PrivateMediaStorage",
            "OPTIONS": {"location": str(tmp_path / "private")},
        },
        "private": {
            "BACKEND": "base.media.PrivateMediaStorage",
            "OPTIONS": {"location": str(tmp_path / "private")},
        },
        "public": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path / "public"), "base_url": "/media/"},
        },
    }
    for model in apps.get_models():
        for field in model._meta.fields:
            if isinstance(field, FileField):
                alias = (
                    "public"
                    if getattr(field, "_storage_callable", None) is get_public_storage
                    else "private"
                )
                monkeypatch.setattr(field, "storage", storages[alias])
    return tmp_path
