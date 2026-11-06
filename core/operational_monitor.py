"""Monitor executável fora do broker para detectar também a própria indisponibilidade."""

import hashlib
import ipaddress
import json
import os
import socket
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from scripts.pilot_backup import BackupError, check_freshness


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_operational_url(request, timeout=5):
    return build_opener(NoRedirect()).open(request, timeout=timeout)


def safe_operational_url(url):
    parsed = urlsplit(url)
    loopback = parsed.hostname == "localhost"
    try:
        loopback = loopback or ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        pass
    if (
        parsed.username
        or parsed.password
        or parsed.scheme not in {"http", "https"}
        or (parsed.scheme == "http" and not loopback)
    ):
        raise BackupError("Monitor exige HTTPS ou receptor loopback explícito.")
    return url


def probe_service(url):
    try:
        with open_operational_url(  # noqa: S310 -- scheme and host policy validated
            safe_operational_url(url), timeout=5
        ) as response:  # noqa: S310 -- scheme and host policy validated
            return response.status == 200
    except (OSError, ValueError, BackupError):
        return False


def probe_broker(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"amqp", "amqps"} or not parsed.hostname:
        return False
    try:
        with socket.create_connection(
            (parsed.hostname, parsed.port or (5671 if parsed.scheme == "amqps" else 5672)),
            timeout=3,
        ):
            return True
    except OSError:
        return False


def monitor_snapshot(*, backup, service_url, broker_url, communication_health):
    codes = []
    try:
        backup_age = check_freshness(backup)
    except (BackupError, OSError, ValueError, KeyError, zipfile.BadZipFile):
        backup_age = None
        codes.append("backup_unavailable_or_stale")
    if not probe_service(service_url):
        codes.append("service_unavailable")
    if not probe_broker(broker_url):
        codes.append("broker_unavailable")
    if communication_health.get("database_unavailable"):
        codes.append("database_or_outbox_health_unavailable")
    if communication_health["schools_with_overdue_outbox"]:
        codes.append("outbox_overdue")
    return {"codes": codes, "backup_age_seconds": backup_age, **communication_health}


def notify_monitor(snapshot, *, alert_url, state_path):
    state_path = Path(state_path)
    if state_path.parent.stat().st_mode & 0o077 or state_path.is_symlink():
        raise BackupError("Estado do monitor exige diretório privado sem link simbólico.")
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    fingerprint = hashlib.sha256(json.dumps(sorted(snapshot["codes"])).encode()).hexdigest()
    if state.get("fingerprint") == fingerprint:
        return state["reference"], False
    reference = str(uuid.uuid4())
    payload = {
        "reference": reference,
        "codes": snapshot["codes"],
        "status": "attention_required" if snapshot["codes"] else "recovered",
    }
    request = Request(  # noqa: S310 -- scheme and host policy validated
        safe_operational_url(alert_url),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if token := os.environ.get("MONITOR_ALERT_TOKEN"):
        request.add_header("Authorization", f"Bearer {token}")
    with open_operational_url(
        request, timeout=5
    ) as response:  # noqa: S310 -- scheme and host policy validated
        if response.status not in {200, 201, 202, 204}:
            raise BackupError("Receptor não confirmou o alerta.")
    descriptor = os.open(state_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump({"fingerprint": fingerprint, "reference": reference}, output)
    return reference, True
