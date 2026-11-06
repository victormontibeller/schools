"""Testes de segurança do reset descartável de desenvolvimento."""

import os
import subprocess
import sys
from pathlib import Path


def test_reset_dev_rejects_remote_database_before_running_psql(tmp_path):
    root = Path(__file__).resolve().parents[2]
    marker = tmp_path / "psql-was-called"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_psql = fake_bin / "psql"
    fake_psql.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    fake_psql.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "PYTHON_BIN": sys.executable,
        "CONFIRM_RESET_DEV": "RESET",
        "DB_HOST": "db.example.test",
        "DEV_PLATFORM_ADMIN_PASSWORD": "unused",
        "DEV_DEMO_ADMIN_PASSWORD": "unused",
    }

    result = subprocess.run(  # noqa: S603 -- comando fixo do próprio repositório
        ["/bin/sh", "scripts/reset_dev.sh"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "DB_HOST deve apontar para um PostgreSQL local" in result.stderr
    assert not marker.exists()
