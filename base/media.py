"""Armazenamento e entrega segura de mídia, sem dependências de domínio."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from django.core.files.storage import FileSystemStorage, storages
from django.db import transaction
from django.http import FileResponse
from django.utils.deconstruct import deconstructible

from base import context

_SAFE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


class PrivateMediaStorage(FileSystemStorage):
    """Storage local deliberadamente incapaz de produzir URL pública."""

    def url(self, name: str) -> str:
        raise ValueError("Arquivos privados não possuem URL pública.")


@deconstructible
class TenantMediaPath:
    """Gera paths sem PII: schema/categoria/UUID.extensão."""

    def __init__(self, category: str) -> None:
        self.category = category.strip("/")

    def __call__(self, instance, filename: str) -> str:
        schema = getattr(instance, "schema_name", "") or context.current_tenant.get()
        schema = schema if schema and schema != "public" else "platform"
        extension = Path(filename).suffix.lower()
        if extension not in _SAFE_EXTENSIONS:
            extension = ""
        return f"{schema}/{self.category}/{uuid.uuid4().hex}{extension}"


def get_public_storage():
    """Resolve o storage público sem congelar paths locais em migrations."""
    return storages["public"]


def get_private_storage():
    """Resolve o storage privado sem congelar paths locais em migrations."""
    return storages["private"]


school_logo_path = TenantMediaPath("logos/schools")
business_unit_logo_path = TenantMediaPath("logos/business-units")
user_avatar_path = TenantMediaPath("avatars/users")
student_photo_path = TenantMediaPath("photos/students")
guardian_avatar_path = TenantMediaPath("avatars/guardians")
student_document_path = TenantMediaPath("documents/enrollments")
attendance_document_path = TenantMediaPath("documents/attendance")


def private_file_response(field_file, *, as_attachment: bool) -> FileResponse:
    """Entrega um arquivo privado com headers que impedem cache e sniffing."""
    content_type = mimetypes.guess_type(field_file.name)[0] or "application/octet-stream"
    response = FileResponse(
        field_file.open("rb"),
        as_attachment=as_attachment,
        filename=Path(field_file.name).name,
        content_type=content_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def delete_replaced_file_after_commit(storage, old_name: str, new_name: str) -> None:
    """Remove a versão substituída somente depois que a escrita for confirmada."""
    if not old_name or old_name == new_name:
        return
    transaction.on_commit(lambda: storage.delete(old_name))
