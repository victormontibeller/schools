"""Backup consistente sob quiescência e restauração exclusivamente em destinos novos.

Uso: python scripts/pilot_backup.py --help. Credenciais somente em PG* ou DB* no ambiente.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path


class BackupError(Exception):
    """Falha operacional segura, sem stderr do provedor ou credenciais."""


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def pg_run(binary, arguments):
    environment = os.environ.copy()
    for target, source in (
        ("PGHOST", "DB_HOST"),
        ("PGPORT", "DB_PORT"),
        ("PGUSER", "DB_USER"),
        ("PGPASSWORD", "DB_PASSWORD"),
    ):
        if source in environment:
            environment[target] = environment[source]
    executable = (
        Path(environment.get("PG_BIN", "")) / binary if environment.get("PG_BIN") else binary
    )
    result = subprocess.run(  # noqa: S603 -- fixed PG binary, separate arguments
        [str(executable), *arguments], env=environment, capture_output=True, check=False
    )
    if result.returncode:
        raise BackupError(f"Falha em {binary}; destino não foi liberado para uso.")
    return result.stdout.decode().strip()


def valid_database(name):
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name or ""):
        raise BackupError("Nome de banco inválido.")
    return name


def private_parent(path):
    if not path.parent.is_dir() or path.parent.stat().st_mode & 0o077:
        raise BackupError("O diretório pai precisa existir e ter permissão 0700.")
    if path.exists() or path.is_symlink():
        raise BackupError("O destino já existe. Escolha um destino novo.")


def create_backup(*, database, media, output, quiescent):
    if not quiescent:
        raise BackupError("Confirme a interrupção de todos os escritores de banco e mídia.")
    valid_database(database)
    output, media = Path(output), Path(media)
    private_parent(output)
    if output.parent.resolve().is_relative_to(media.resolve()):
        raise BackupError("Backup deve ficar fora da árvore de mídia.")
    if not media.is_dir() or media.is_symlink():
        raise BackupError("A raiz de mídia deve ser um diretório existente sem link simbólico.")
    started = dt.datetime.now(dt.UTC)
    manifest = {
        "format": "school-manager-backup-v1",
        "database": database,
        "recovery_point_utc": started.isoformat(),
        "quiescent": True,
        "files": {},
        "postgres_version": pg_run("pg_dump", ["--version"]),
    }
    with tempfile.TemporaryDirectory(prefix=".backup-", dir=output.parent) as work:
        work = Path(work)
        dump = work / "database.dump"
        pg_run(
            "pg_dump",
            [
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(dump),
                "--dbname",
                database,
            ],
        )
        package = work / "backup.zip"
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(dump, "database.dump")
            manifest["files"]["database.dump"] = digest_file(dump)
            for source in sorted(media.rglob("*")):
                if source.is_symlink():
                    raise BackupError("Mídia contém link simbólico; cópia recusada.")
                if not source.is_file():
                    continue
                name = "media/" + source.relative_to(media).as_posix()
                archive.write(source, name)
                manifest["files"][name] = digest_file(source)
            manifest["completed_at_utc"] = dt.datetime.now(dt.UTC).isoformat()
            archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        package.chmod(0o600)
        os.link(package, output)
    return manifest


def verify_backup(archive):
    names = archive.namelist()
    if len(names) != len(set(names)) or "manifest.json" not in names:
        raise BackupError("Arquivo inválido ou com membros duplicados.")
    manifest = json.loads(archive.read("manifest.json"))
    if manifest.get("format") != "school-manager-backup-v1" or not manifest.get("quiescent"):
        raise BackupError("Manifesto de backup inválido.")
    expected = set(manifest["files"]) | {"manifest.json"}
    if expected != set(names) or "database.dump" not in expected:
        raise BackupError("Manifesto e arquivos não correspondem.")
    for entry in archive.infolist():
        path = Path(entry.filename)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in entry.filename
            or stat.S_ISLNK(entry.external_attr >> 16)
        ):
            raise BackupError("Caminho inseguro no pacote.")
        if entry.filename not in {
            "manifest.json",
            "database.dump",
        } and not entry.filename.startswith("media/"):
            raise BackupError("Membro fora da allowlist do backup.")
        if entry.filename == "manifest.json":
            continue
        digest = hashlib.sha256()
        with archive.open(entry) as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != manifest["files"][entry.filename]:
            raise BackupError("Checksum inválido; restauração recusada.")
    return manifest


def restore_backup(*, source, database, directory):
    valid_database(database)
    destination = Path(directory)
    private_parent(destination)
    started = time.monotonic()
    with zipfile.ZipFile(source) as archive:
        manifest = verify_backup(archive)
        if database == manifest["database"]:
            raise BackupError("Restauração no banco de origem é proibida.")
        # createdb fails if it already exists; never DROP or overwrite an existing database.
        pg_run("createdb", ["--template=template0", database])
        destination.mkdir(mode=0o700)
        for entry in archive.infolist():
            target = destination / entry.filename
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with archive.open(entry) as source_file, target.open("xb") as output:
                target.chmod(0o600)
                shutil.copyfileobj(source_file, output)
    pg_run(
        "pg_restore",
        [
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-acl",
            "--dbname",
            database,
            str(destination / "database.dump"),
        ],
    )
    point = dt.datetime.fromisoformat(manifest["recovery_point_utc"])
    proof = {
        "database": database,
        "recovery_point_utc": point.isoformat(),
        "recovery_point_age_seconds": (dt.datetime.now(dt.UTC) - point).total_seconds(),
        "restore_duration_seconds": time.monotonic() - started,
        "file_checksums_verified": len(manifest["files"]),
        "business_validation_required": True,
        "reopening_authorized": False,
    }
    proof_path = destination / "restore-proof.json"
    proof_path.write_text(json.dumps(proof, sort_keys=True, indent=2))
    proof_path.chmod(0o600)
    return proof


def check_freshness(source, maximum_age_seconds=3600):
    with zipfile.ZipFile(source) as archive:
        manifest = verify_backup(archive)
    age = (
        dt.datetime.now(dt.UTC) - dt.datetime.fromisoformat(manifest["recovery_point_utc"])
    ).total_seconds()
    if age < 0 or age > maximum_age_seconds:
        raise BackupError("Ponto de recuperação vencido ou relógio inconsistente.")
    return age


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    backup = actions.add_parser("backup")
    backup.add_argument("--database", required=True)
    backup.add_argument("--media", required=True)
    backup.add_argument("--output", required=True)
    backup.add_argument("--writers-stopped", action="store_true")
    restore = actions.add_parser("restore")
    restore.add_argument("--source", required=True)
    restore.add_argument("--database", required=True)
    restore.add_argument("--directory", required=True)
    check = actions.add_parser("check")
    check.add_argument("--source", required=True)
    check.add_argument("--maximum-age-seconds", type=int, default=3600)
    options = parser.parse_args()
    try:
        if options.action == "backup":
            create_backup(
                database=options.database,
                media=options.media,
                output=options.output,
                quiescent=options.writers_stopped,
            )
        elif options.action == "restore":
            restore_backup(
                source=options.source, database=options.database, directory=options.directory
            )
        else:
            check_freshness(options.source, options.maximum_age_seconds)
    except (BackupError, OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(
            1,
            f"Operação não concluída ({type(exc).__name__}). Consulte o runbook; não reabra a escola.\n",
        )
    parser.exit(
        0,
        "Operação concluída. A restauração ainda exige validação e reconciliação antes da reabertura.\n",
    )


if __name__ == "__main__":
    main()
