#!/usr/bin/env python3
"""Falha diante de qualquer violação das fronteiras arquiteturais."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.access_catalog import APP_MODULES  # noqa: E402

LOCAL_APPS = {
    "academic_calendar",
    "accounts",
    "activities",
    "addresses",
    "agenda",
    "attendance",
    "audit",
    "base",
    "classes",
    "core",
    "dashboard",
    "enrollments",
    "financeiro",
    "guardians",
    "locations",
    "notifications",
    "rooms",
    "student_diary",
    "students",
    "teachers",
    "tenancy",
}
RAW_SQL_CALLS = {"cursor", "execute", "executemany", "raw"}
ORM_MANAGERS = {"objects", "all_objects"}
ACCESS_SPECIAL_APPS = {"accounts", "addresses", "audit", "base", "core", "tenancy"}


def _python_files():
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if any(part in {".git", ".venv", "migrations", "tests"} for part in relative.parts):
            continue
        yield path, relative.as_posix()


def _imported_modules(node: ast.AST):
    if isinstance(node, ast.Import):
        yield from (alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        yield node.module


def scan() -> set[str]:
    """Retorna chaves estáveis das violações existentes."""
    violations: set[str] = set()
    for path, relative in _python_files():
        source = path.read_text(encoding="utf-8")
        if len(source.splitlines()) > 400:
            violations.add(f"{relative}:module-too-large")
        source_app = relative.split("/", maxsplit=1)[0]
        is_view_module = relative.endswith("views.py") or "/views/" in relative
        is_service_module = relative.endswith("services.py") or "/services/" in relative
        if (
            (is_view_module or is_service_module)
            and source_app in LOCAL_APPS
            and source_app not in APP_MODULES
            and source_app not in ACCESS_SPECIAL_APPS
        ):
            violations.add(f"{relative}:missing-access-catalog:{source_app}")
        tree = ast.parse(source, filename=relative)
        for node in ast.walk(tree):
            for module in _imported_modules(node):
                target_app = module.split(".", maxsplit=1)[0]
                imports_model = module == f"{target_app}.models"
                if is_view_module and imports_model and target_app in LOCAL_APPS:
                    violations.add(f"{relative}:view-imports-model:{module}")
                if source_app == "base" and target_app in LOCAL_APPS and target_app != "base":
                    violations.add(f"{relative}:base-depends-on-app:{module}")
                if (
                    imports_model
                    and source_app in LOCAL_APPS
                    and target_app in LOCAL_APPS
                    and target_app != "base"
                    and target_app != source_app
                ):
                    violations.add(f"{relative}:cross-domain-model:{module}")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in RAW_SQL_CALLS
            ):
                violations.add(f"{relative}:raw-sql:{node.func.attr}")
            if is_view_module and isinstance(node, ast.Attribute) and node.attr in ORM_MANAGERS:
                violations.add(f"{relative}:orm-in-view:{node.attr}")
    return violations


def main() -> int:
    current = scan()
    if current:
        print("Violações de arquitetura:")
        for violation in sorted(current):
            print(f"- {violation}")
        return 1
    print("Contratos de importação conformes: zero violações.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
