"""Testes do contrato de migrations descartáveis antes da produção."""

from pathlib import Path

import pytest

from scripts.check_preproduction_contracts import ALLOWED_DATA_MIGRATIONS, scan


def _write_migration(root: Path, relative: str, body: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "from django.db import migrations\n\n"
        "def seed(apps, schema_editor):\n"
        "    pass\n\n"
        "class Migration(migrations.Migration):\n"
        f"{body}\n",
        encoding="utf-8",
    )


def _write_valid_seeds(root: Path) -> None:
    for relative in ALLOWED_DATA_MIGRATIONS:
        _write_migration(
            root,
            relative,
            "    dependencies = []\n"
            "    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]",
        )


def test_scan_accepts_allowlisted_runpython_only_seeds(tmp_path):
    _write_valid_seeds(tmp_path)

    assert scan(tmp_path) == set()


@pytest.mark.parametrize(
    "extra_operation",
    [
        "RunSQL('SELECT 1')",
        "CreateModel(name='X', fields=[])",
        "AddField(model_name='x', name='y', field=None)",
    ],
)
def test_scan_rejects_extra_operation_in_allowlisted_seed(tmp_path, extra_operation):
    _write_valid_seeds(tmp_path)
    relative = "locations/migrations/0002_seed_locations.py"
    _write_migration(
        tmp_path,
        relative,
        "    dependencies = []\n"
        f"    operations = [migrations.RunPython(seed), migrations.{extra_operation}]",
    )

    assert f"{relative}:allowed-seed-must-use-only-runpython" in scan(tmp_path)


def test_scan_finds_nested_evolutionary_migration(tmp_path):
    _write_valid_seeds(tmp_path)
    relative = "packages/school/migrations/0002_change.py"
    _write_migration(tmp_path, relative, "    dependencies = []\n    operations = []")

    assert f"{relative}:evolutionary-migration-forbidden" in scan(tmp_path)


def test_scan_ignores_migrations_inside_git_and_virtualenv(tmp_path):
    _write_valid_seeds(tmp_path)
    for relative in (
        ".git/vendor/migrations/0002_change.py",
        ".venv/package/migrations/0002_change.py",
    ):
        _write_migration(tmp_path, relative, "    dependencies = []\n    operations = []")

    assert scan(tmp_path) == set()


def test_scan_rejects_replaces_even_on_initial_migration(tmp_path):
    _write_valid_seeds(tmp_path)
    relative = "sample/migrations/0001_initial.py"
    _write_migration(
        tmp_path,
        relative,
        "    initial = True\n"
        "    replaces: list = [('sample', '0001_old')]\n"
        "    operations = []",
    )

    assert f"{relative}:replaces-forbidden" in scan(tmp_path)


def test_scan_requires_both_allowlisted_seeds(tmp_path):
    present = "locations/migrations/0002_seed_locations.py"
    _write_migration(
        tmp_path,
        present,
        "    dependencies = []\n    operations = [migrations.RunPython(seed)]",
    )
    missing = "student_diary/migrations/0002_seed_agenda_items.py"

    assert f"{missing}:required-seed-missing" in scan(tmp_path)
