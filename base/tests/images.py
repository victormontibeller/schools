"""Helpers de imagens válidas para testes de upload."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def png_upload(name: str = "avatar.png") -> SimpleUploadedFile:
    """Retorna um PNG 1x1 íntegro."""
    buffer = BytesIO()
    Image.new("RGB", (1, 1), color="white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")
