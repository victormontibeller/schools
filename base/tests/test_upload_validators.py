"""Testes de validação do conteúdo real de uploads."""

from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from pypdf import PdfWriter

from base.upload_validators import (
    DOCUMENT_MAX_BYTES,
    IMAGE_MAX_BYTES,
    validate_document_upload,
    validate_image_upload,
)


def _image_upload(image_format: str = "PNG", name: str = "image.png"):
    stream = BytesIO()
    Image.new("RGB", (2, 2), "white").save(stream, format=image_format)
    return SimpleUploadedFile(name, stream.getvalue())


def test_image_validator_accepts_png_and_rewinds_file():
    upload = _image_upload()
    validate_image_upload(upload)
    assert upload.tell() == 0


@pytest.mark.parametrize(
    ("upload", "message"),
    [
        (SimpleUploadedFile("large.png", b"x" * (IMAGE_MAX_BYTES + 1)), "5 MiB"),
        (SimpleUploadedFile("broken.png", b"not-an-image"), "inválido"),
        (_image_upload("GIF", "image.gif"), "não permitido"),
    ],
)
def test_image_validator_rejects_unsafe_content(upload, message):
    with pytest.raises(ValidationError, match=message):
        validate_image_upload(upload)


def test_document_validator_accepts_valid_pdf_and_image():
    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=10, height=10)
    writer.write(stream)
    pdf = SimpleUploadedFile("document.pdf", stream.getvalue())

    validate_document_upload(pdf)
    validate_document_upload(_image_upload())
    assert pdf.tell() == 0


@pytest.mark.parametrize(
    "upload",
    [
        SimpleUploadedFile("large.pdf", b"x" * (DOCUMENT_MAX_BYTES + 1)),
        SimpleUploadedFile("document.exe", b"MZ"),
        SimpleUploadedFile("fake.pdf", b"not a pdf"),
        SimpleUploadedFile("broken.pdf", b"%PDF-broken"),
    ],
)
def test_document_validator_rejects_unsafe_content(upload):
    with pytest.raises(ValidationError):
        validate_document_upload(upload)
