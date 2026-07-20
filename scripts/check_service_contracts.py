#!/usr/bin/env python3
"""Falha quando uma mutação pública de service não declara seu contrato."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from base.services import MUTATION_PREFIXES  # noqa: E402

EXCLUDED_PARTS = {".git", ".venv", "migrations", "tests"}
EXPLICIT_COMMAND_DECORATORS = {"service_command", "system_command"}
MUTATING_METHODS = {
    "bulk_create",
    "bulk_update",
    "create",
    "delete",
    "get_or_create",
    "restore",
    "save",
    "soft_delete",
    "update",
    "update_or_create",
}
MUTATING_HELPERS = {"_deactivate", "_record_audit"}


def _service_files(root: Path):
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if relative.name.endswith("services.py") or "services" in relative.parts[:-1]:
            yield path, relative.as_posix()


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _name(node.func)
    return ""


def _root_name(node: ast.AST) -> str:
    while isinstance(node, ast.Attribute | ast.Call):
        node = node.value if isinstance(node, ast.Attribute) else node.func
    return node.id if isinstance(node, ast.Name) else ""


def _has_explicit_command(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_name(decorator) in EXPLICIT_COMMAND_DECORATORS for decorator in node.decorator_list)


def _is_mutation(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Attribute):
            continue
        if child.func.attr == "delete" and _root_name(child.func.value) == "cache":
            continue
        if child.func.attr in MUTATING_HELPERS | MUTATING_METHODS:
            return True
    return False


def _command_classes(trees: list[tuple[str, ast.Module]]) -> set[str]:
    """Resolve services e mixins participantes por seu grafo de herança."""
    classes = {
        node.name: {_name(base) for base in node.bases}
        for _, tree in trees
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }
    derived = {name for name, bases in classes.items() if "BaseService" in bases}
    while True:
        discovered = {
            name for name, bases in classes.items() if name not in derived and bases & derived
        }
        if not discovered:
            break
        derived.update(discovered)

    participants = set(derived)
    pending = list(derived)
    while pending:
        for base in classes.get(pending.pop(), set()):
            if base in classes and base not in participants:
                participants.add(base)
                pending.append(base)
    return participants


def scan(root: Path = ROOT) -> set[str]:
    """Retorna violações estáveis encontradas nos services do diretório."""
    violations: set[str] = set()
    trees = [
        (relative, ast.parse(path.read_text(encoding="utf-8"), filename=relative))
        for path, relative in _service_files(root)
    ]
    command_classes = _command_classes(trees)
    for relative, tree in trees:
        for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            if class_node.name not in command_classes:
                continue
            for method in class_node.body:
                if not isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                if method.name.startswith("_") or not _is_mutation(method):
                    continue
                declared = method.name.startswith(MUTATION_PREFIXES) or _has_explicit_command(
                    method
                )
                if not declared:
                    violations.add(f"{relative}:{method.lineno}:{method.name}:undeclared-command")
    return violations


def main() -> int:
    """Imprime as violações e retorna status adequado para uso no CI."""
    violations = scan()
    if violations:
        print("Violações de comandos de service:")
        for violation in sorted(violations):
            print(f"- {violation}")
        return 1
    print("Contratos de comandos de service conformes: zero violações.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
