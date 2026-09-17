"""Validação e normalização compartilhada de fotografias e logotipos."""

import warnings
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageCms, ImageOps

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 25_000_000
FORMATS = {"JPEG", "PNG", "WEBP"}


def decoded_image(upload) -> Image.Image:
    """Decodifica integralmente um upload limitado, preservando seu cursor inicial."""
    try:
        upload.seek(0)
        payload = upload.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ValidationError("A imagem deve ter no máximo 5 MiB.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as source:
                if source.format not in FORMATS:
                    raise ValidationError("Formato de imagem não permitido.")
                if source.width * source.height > MAX_PIXELS:
                    raise ValidationError("A imagem deve ter no máximo 25 megapixels.")
                if getattr(source, "is_animated", False):
                    raise ValidationError("Imagens animadas não são permitidas.")
                source.verify()
            with Image.open(BytesIO(payload)) as source:
                source.load()
                return ImageOps.exif_transpose(source).copy()
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("Arquivo de imagem inválido.") from exc
    finally:
        upload.seek(0)


def normalize_image(upload, *, logo: bool = False) -> ContentFile:
    """Produz somente WebP limpo, sRGB, proporcional e sem ampliar a imagem."""
    image = decoded_image(upload)
    alpha = (
        image.convert("RGBA").getchannel("A")
        if ("A" in image.getbands() or "transparency" in image.info)
        else None
    )
    profile = image.info.get("icc_profile")
    try:
        if profile:
            if image.mode not in {"RGB", "CMYK", "LAB", "L"}:
                image = image.convert("RGB")
            image = ImageCms.profileToProfile(
                image,
                ImageCms.ImageCmsProfile(BytesIO(profile)),
                ImageCms.createProfile("sRGB"),
                outputMode="RGB",
            )
        else:
            image = image.convert("RGB")
        if alpha is not None:
            image.putalpha(alpha)
        limit = 1024 if logo else 512
        image.thumbnail((limit, limit), Image.Resampling.LANCZOS)
        # Recriar os pixels elimina EXIF, ICC, comentários e metadados do original.
        clean = Image.new(image.mode, image.size)
        clean.paste(image)
        output = BytesIO()
        clean.save(output, format="WEBP", lossless=logo, quality=85, method=6)
        payload = output.getvalue()
        with Image.open(BytesIO(payload)) as verified:
            verified.load()
            if (
                verified.format != "WEBP"
                or verified.size != clean.size
                or verified.info.get("exif")
            ):
                raise ValidationError("Não foi possível processar a imagem.")
        return ContentFile(payload, name="image.webp")
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("Não foi possível processar a imagem.") from exc
