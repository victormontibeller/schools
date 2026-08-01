#!/usr/bin/env python3
"""Valida o histórico descartável de migrations enquanto o produto está em pré-produção."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_DATA_MIGRATIONS = {
    "locations/migrations/0002_seed_locations.py",
    "student_diary/migrations/0002_seed_agenda_items.py",
}
EXCLUDED_PARTS = {".git", ".venv"}


def _migration_files(root: Path):
    """Itera pelas migrations próprias versionadas pelo projeto."""
    for path in root.rglob("migrations/[0-9]*.py"):
        relative = path.relative_to(root)
        if not any(part in EXCLUDED_PARTS for part in relative.parts):
            yield path, relative.as_posix()


def _migration_class(tree: ast.Module) -> ast.ClassDef | None:
    return next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Migration"),
        None,
    )


def _assigned_names(node: ast.ClassDef) -> dict[str, ast.AST]:
    assignments = {}
    for statement in node.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            target = statement.target
            value = statement.value
        else:
            continue
        if isinstance(target, ast.Name) and value is not None:
            assignments[target.id] = value
    return assignments


def _is_true(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _operation_names(node: ast.AST | None) -> list[str | None] | None:
    """Extrai chamadas `migrations.<Operation>` da lista declarada pela migration."""
    if not isinstance(node, ast.List | ast.Tuple):
        return None
    names: list[str | None] = []
    for operation in node.elts:
        if (
            isinstance(operation, ast.Call)
            and isinstance(operation.func, ast.Attribute)
            and isinstance(operation.func.value, ast.Name)
            and operation.func.value.id == "migrations"
        ):
            names.append(operation.func.attr)
        else:
            names.append(None)
    return names


def scan(root: Path = ROOT) -> set[str]:
    """Retorna violações estáveis da política de migrations pré-produção."""
    violations: set[str] = set()
    discovered: set[str] = set()
    for path, relative in _migration_files(root):
        discovered.add(relative)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        migration = _migration_class(tree)
        if migration is None:
            violations.add(f"{relative}:missing-migration-class")
            continue
        assignments = _assigned_names(migration)
        if "replaces" in assignments:
            violations.add(f"{relative}:replaces-forbidden")

        is_allowed_seed = relative in ALLOWED_DATA_MIGRATIONS
        is_initial = _is_true(assignments.get("initial"))
        operations = _operation_names(assignments.get("operations"))
        if not is_initial and not is_allowed_seed:
            violations.add(f"{relative}:evolutionary-migration-forbidden")
        if (
            is_initial
            and operations
            and any(operation in {"RunPython", "RunSQL"} for operation in operations)
        ):
            violations.add(f"{relative}:initial-must-be-structural")
        if is_allowed_seed and (
            not operations or any(operation != "RunPython" for operation in operations)
        ):
            violations.add(f"{relative}:allowed-seed-must-use-only-runpython")

    for missing in ALLOWED_DATA_MIGRATIONS - discovered:
        violations.add(f"{missing}:required-seed-missing")
    return violations


def main() -> int:
    """Exibe violações e retorna status adequado para CI."""
    violations = sorted(scan())
    if violations:
        print("Pre-production migration contract violations:")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    migration_count = sum(1 for _ in _migration_files(ROOT))
    print(f"Pre-production migration contracts: OK ({migration_count} migrations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
