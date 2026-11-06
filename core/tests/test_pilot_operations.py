"""Guardas de ambiente, backup, restauração e alertas sem conteúdo pessoal."""

import hashlib
import json
import zipfile
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured

from core.fictitious import TEMPORARY_ROOT, validate_configuration
from core.operational_monitor import NoRedirect, monitor_snapshot, safe_operational_url
from scripts.pilot_backup import BackupError, create_backup, restore_backup, verify_backup


def valid_configuration():
    root = TEMPORARY_ROOT / "schools-operation-unit"
    return {
        "enabled": True,
        "environment": "development",
        "debug": True,
        "database": {
            "NAME": "schools_pilot_isolated",
            "HOST": "127.0.0.1",
            "ENGINE": "django_tenants.postgresql_backend",
        },
        "directory": root,
        "media_root": root / "media",
        "port": 18080,
        "platform_domain": "platform.localhost",
        "base_domain": "localhost",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"environment": "production"},
        {"debug": False},
        {"database": {"HOST": "remote", "NAME": "schools_pilot_x"}},
        {"directory": "/"},
        {"media_root": "/"},
        {"base_domain": "example.com"},
        {"port": 80},
    ],
)
def test_fictitious_configuration_rejects_nonlocal_or_production_context(change):
    config = valid_configuration()
    validate_configuration(**config)
    with pytest.raises(ImproperlyConfigured):
        validate_configuration(**(config | change))


def archive_fixture(
    path, *, name="media/private/synthetic.txt", content=b"synthetic", checksum=None
):
    with zipfile.ZipFile(path, "w") as archive:
        files = {
            "database.dump": hashlib.sha256(b"dump").hexdigest(),
            name: checksum or hashlib.sha256(content).hexdigest(),
        }
        archive.writestr("database.dump", b"dump")
        archive.writestr(name, content)
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": "school-manager-backup-v1",
                    "quiescent": True,
                    "database": "source_db",
                    "recovery_point_utc": "2026-01-01T00:00:00+00:00",
                    "files": files,
                }
            ),
        )


@pytest.mark.parametrize(
    "name", ["../outside", "/absolute", "media/../outside", "unexpected.txt", "media\\outside"]
)
def test_restore_rejects_unsafe_members_before_creating_database(tmp_path, name):
    source = tmp_path / "source.zip"
    archive_fixture(source, name=name)
    tmp_path.chmod(0o700)
    with patch("scripts.pilot_backup.pg_run") as pg, pytest.raises(BackupError):
        restore_backup(source=source, database="new_db", directory=tmp_path / "restore")
    pg.assert_not_called()
    assert not (tmp_path / "restore").exists()


def test_backup_refuses_output_inside_media_before_invoking_postgres(tmp_path):
    media = tmp_path / "media"
    folder = media / "private"
    folder.mkdir(parents=True, mode=0o700)
    with patch("scripts.pilot_backup.pg_run") as pg, pytest.raises(BackupError, match="fora"):
        create_backup(
            database="source_db", media=media, output=folder / "backup.zip", quiescent=True
        )
    pg.assert_not_called()


def test_backup_requires_quiescence_and_detects_corruption(tmp_path):
    with pytest.raises(BackupError, match="escritores"):
        create_backup(
            database="source_db", media=tmp_path, output=tmp_path / "b.zip", quiescent=False
        )
    source = tmp_path / "source.zip"
    archive_fixture(source, checksum="wrong")
    with zipfile.ZipFile(source) as archive, pytest.raises(BackupError, match="Checksum"):
        verify_backup(archive)


def test_restore_refuses_source_database_and_existing_directory(tmp_path):
    tmp_path.chmod(0o700)
    source = tmp_path / "source.zip"
    archive_fixture(source)
    with patch("scripts.pilot_backup.pg_run") as pg, pytest.raises(BackupError, match="origem"):
        restore_backup(source=source, database="source_db", directory=tmp_path / "new")
    pg.assert_not_called()
    with pytest.raises(BackupError):
        restore_backup(source=source, database="new_db", directory=tmp_path)


def test_monitor_includes_database_and_truncated_backup_failures_without_exception_details(
    tmp_path,
):
    source = tmp_path / "truncated.zip"
    source.write_bytes(b"truncated")
    with (
        patch("core.operational_monitor.probe_service", return_value=False),
        patch("core.operational_monitor.probe_broker", return_value=False),
    ):
        result = monitor_snapshot(
            backup=source,
            service_url="http://127.0.0.1/health/",
            broker_url="amqp://127.0.0.1",
            communication_health={
                "database_unavailable": True,
                "pending_deliveries": 0,
                "schools_with_overdue_outbox": 1,
            },
        )
    assert set(result["codes"]) == {
        "backup_unavailable_or_stale",
        "database_or_outbox_health_unavailable",
        "service_unavailable",
        "broker_unavailable",
        "outbox_overdue",
    }


def test_monitor_rejects_insecure_targets_and_never_follows_redirects():
    for target in ("file:///etc/passwd", "http://example.com", "https://secret@example.com"):
        with pytest.raises(BackupError):
            safe_operational_url(target)
    assert safe_operational_url("http://127.0.0.1:12345/")
    assert (
        NoRedirect().redirect_request(None, None, 302, "redirect", {}, "http://other.invalid")
        is None
    )


def test_axes_reference_and_log_filter_never_include_credentials_headers_or_path():
    import logging
    from types import SimpleNamespace

    from core.authentication_logging import axes_client_reference
    from core.request_security import SafeHttpLogFilter

    marker = "PRIVATE-MARKER@example.test"
    request = SimpleNamespace(resolver_match=SimpleNamespace(view_name="login"))
    reference = axes_client_reference(marker, marker, marker, marker, request)
    assert "route=login" in reference and marker not in reference
    record = logging.LogRecord(
        "axes.handlers.database", logging.WARNING, "", 0, "AXES failure %s", (marker,), None
    )
    record.user_agent = marker
    record.path_info = marker
    assert SafeHttpLogFilter().filter(record)
    assert marker not in str(record.__dict__)
    assert record.getMessage() == "authentication_control_event"
