"""Arquivo privado de portabilidade; mídia por hash e sem caminhos de origem."""

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from base.exceptions import BusinessRuleViolationError
from core.export_selectors import FIELDS, MEDIA_FIELDS, SchoolExportSelector


def json_bytes(value):
    return json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False, sort_keys=True).encode()


def build_export_archive(school, destination):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink() or not destination.parent.is_dir():
        raise BusinessRuleViolationError("Escolha um arquivo novo em diretório privado existente.")
    if destination.parent.stat().st_mode & 0o077:
        raise BusinessRuleViolationError(
            "O diretório de exportação deve permitir acesso somente ao proprietário (0700)."
        )
    descriptor, staging_name = tempfile.mkstemp(prefix=".school-export-", dir=destination.parent)
    os.close(descriptor)
    staging = Path(staging_name)
    manifest = {
        "format": "school-manager-export-v1",
        "schema": school.schema_name,
        "school_id": str(school.pk),
        "created_at": timezone.now(),
        "files": {},
        "counts": {},
        "limitations": [
            "Pacote de portabilidade; não substitui backup restaurável do banco.",
            "Recibos podem ser regenerados a partir dos pagamentos e alocações.",
        ],
    }
    selector = SchoolExportSelector()
    try:
        with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for label in FIELDS:
                count = 0
                filename = f"data/{label}.jsonl"
                digest = hashlib.sha256()
                # Zip members cannot be written concurrently: media is added before this table.
                with tempfile.TemporaryFile() as table:
                    for instance in selector.records(label, school):
                        record = selector.serialize(instance, label)
                        record["media"] = {}
                        for field in MEDIA_FIELDS.get(label, ()):
                            value = getattr(instance, field)
                            if not value:
                                continue
                            record["media"][field] = _add_media(
                                archive, value, manifest, school.schema_name
                            )
                        row = json_bytes(record) + b"\n"
                        table.write(row)
                        digest.update(row)
                        count += 1
                    table.seek(0)
                    with archive.open(filename, "w") as output:
                        while chunk := table.read(1024 * 1024):
                            output.write(chunk)
                manifest["counts"][label] = count
                manifest["files"][filename] = digest.hexdigest()
            archive.writestr("manifest.json", json_bytes(manifest))
        return staging, manifest
    except Exception:
        staging.unlink(missing_ok=True)
        raise


def _add_media(archive, field, manifest, schema):
    from base.media import image_namespace

    name = Path(field.name)
    if (
        name.is_absolute()
        or ".." in name.parts
        or not name.parts
        or name.parts[0] not in {schema, image_namespace(schema)}
    ):
        raise BusinessRuleViolationError("Mídia fora do namespace da escola.")
    try:
        root = Path(field.storage.location).resolve()
        target = root / name
        if not target.resolve().is_relative_to(root) or any(
            item.is_symlink()
            for item in [target, *target.parents]
            if item != root and item.is_relative_to(root)
        ):
            raise BusinessRuleViolationError("Mídia contém caminho simbólico ou externo.")
        with field.storage.open(field.name, "rb") as source, tempfile.TemporaryFile() as copy:
            digest = hashlib.sha256()
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
                copy.write(chunk)
            checksum = digest.hexdigest()
            name = f"media/{checksum}"
            if name not in manifest["files"]:
                copy.seek(0)
                with archive.open(name, "w") as output:
                    while chunk := copy.read(1024 * 1024):
                        output.write(chunk)
                manifest["files"][name] = checksum
            return name
    except (OSError, ValueError):
        raise BusinessRuleViolationError(
            "Exportação interrompida: mídia referenciada ausente ou indisponível."
        ) from None


def publish_export(staging, destination):
    # Hard link is atomic and refuses replacement; both paths are in the same private folder.
    try:
        os.link(staging, destination)
    finally:
        staging.unlink(missing_ok=True)
