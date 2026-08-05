"""Contrato do contexto enviado ao build Docker."""

from pathlib import Path

from pathspec import PathSpec


def test_dockerignore_blocks_sensitive_and_generated_paths():
    """Secrets, estado local e artefatos gerados não entram no contexto."""
    root = Path(__file__).resolve().parents[2]
    spec = PathSpec.from_lines("gitignore", (root / ".dockerignore").read_text().splitlines())

    blocked = {
        ".env",
        ".env.local",
        ".git/config",
        ".venv/bin/python",
        "media/private/student.jpg",
        "local.sqlite3",
        "local.sqlite3-wal",
        "local.sqlite3-shm",
        "local.sqlite3-journal",
        "local.sqlite",
        "local.db-wal",
        ".pytest_cache/CACHEDIR.TAG",
        ".ruff_cache/state",
        ".coverage",
        "htmlcov/index.html",
        "application.log",
        "staticfiles/admin/css/base.css",
        "playwright-report/index.html",
        "test-results/trace.zip",
    }
    assert all(spec.match_file(path) for path in blocked)


def test_dockerignore_preserves_runtime_inputs():
    """Locks, código, templates, migrations, assets e entrypoint permanecem disponíveis."""
    root = Path(__file__).resolve().parents[2]
    spec = PathSpec.from_lines("gitignore", (root / ".dockerignore").read_text().splitlines())
    preserved = {
        "requirements.lock",
        "manage.py",
        "core/settings.py",
        "templates/base.html",
        "students/migrations/0001_initial.py",
        "design_system/refs/duralux/css/school-manager.css",
        "docker/entrypoint.sh",
    }
    assert all((root / path).exists() for path in preserved)
    assert not any(spec.match_file(path) for path in preserved)
