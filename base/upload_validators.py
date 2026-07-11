"""Validadores de tamanho e conteúdo real para uploads."""

from pathlib import Path

from django.core.exceptions import ValidationError

IMAGE_MAX_BYTES = 5 * 1024 * 1024
DOCUMENT_MAX_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def _rewind(upload) -> None:
    """Reposiciona upload quando o objeto suporta seek."""
    if hasattr(upload, "seek"):
        upload.seek(0)


def validate_image_upload(upload) -> None:
    """Aceita somente JPEG, PNG ou WebP íntegros até 5 MiB."""
    if getattr(upload, "size", 0) > IMAGE_MAX_BYTES:
        raise ValidationError("A imagem deve ter no máximo 5 MiB.")
    try:
        from PIL import Image

        _rewind(upload)
        image = Image.open(upload)
        image.verify()
        if image.format not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError("Formato de imagem não permitido.")
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("Arquivo de imagem inválido.") from exc
    finally:
        _rewind(upload)


def validate_document_upload(upload) -> None:
    """Aceita PDF ou imagem íntegra até 10 MiB, independentemente da extensão."""
    if getattr(upload, "size", 0) > DOCUMENT_MAX_BYTES:
        raise ValidationError("O documento deve ter no máximo 10 MiB.")
    suffix = Path(getattr(upload, "name", "")).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        validate_image_upload(upload)
        return
    if suffix != ".pdf":
        raise ValidationError("Envie um arquivo PDF, JPEG, PNG ou WebP.")
    try:
        from pypdf import PdfReader

        _rewind(upload)
        header = upload.read(5)
        _rewind(upload)
        if header != b"%PDF-":
            raise ValidationError("Arquivo PDF inválido.")
        PdfReader(upload, strict=True)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("Arquivo PDF inválido.") from exc
    finally:
        _rewind(upload)
