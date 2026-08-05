"""Verificação determinística dos contratos declarados em ``core.ui_contracts``."""

from __future__ import annotations

import re
from pathlib import Path

from django.urls import NoReverseMatch, reverse

from core.ui_catalog import LIST_PAGE_CATALOG
from core.ui_contracts import (
    CANONICAL_TABS_TEMPLATE,
    DURALUX_REFERENCE_PREFIX,
    LIST_TEMPLATE_CONTRACTS,
    MANUAL_SHELL_ALLOWLIST,
    OBSOLETE_LAYOUT_CLASSES,
    OPERATIONAL_GRID_CONTRACTS,
    SECONDARY_TABLE_ALLOWLIST,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _html_files() -> set[str]:
    ignored_parts = {".venv", "staticfiles", "node_modules"}
    return {
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in PROJECT_ROOT.rglob("*.html")
        if not ignored_parts.intersection(path.parts)
    }


def check_ui_contracts() -> list[str]:
    """Retorna violações determinísticas do contrato visual canônico."""
    errors: list[str] = []
    if set(LIST_TEMPLATE_CONTRACTS) != set(LIST_PAGE_CATALOG):
        errors.append("O catálogo e os templates de listagem possuem rotas diferentes.")
    for route_name, (page_template, table_template) in LIST_TEMPLATE_CONTRACTS.items():
        try:
            reverse(route_name)
        except NoReverseMatch:
            errors.append(f"Rota de listagem inválida: {route_name}")
        page_source = _read(page_template)
        table_source = _read(table_template)
        if '{% extends "list_page_base.html" %}' not in page_source:
            errors.append(f"Listagem fora do shell canônico: {page_template}")
        errors.extend(_check_scroll_contract(table_template, table_source))
    for definition in LIST_PAGE_CATALOG.values():
        for route_name in (definition.search_url, definition.create_url):
            if not route_name:
                continue
            try:
                reverse(route_name)
            except NoReverseMatch:
                errors.append(f"Rota inválida no catálogo de UI: {route_name}")
    for contract in OPERATIONAL_GRID_CONTRACTS:
        page_source = _read(contract.page_template)
        if '{% extends "page_shell_base.html" %}' not in page_source:
            errors.append(f"Grade fora do shell canônico: {contract.page_template}")
        errors.extend(
            _check_scroll_contract(contract.scroll_template, _read(contract.scroll_template))
        )
        table_source = _read(contract.table_template)
        for token in ("sm-sticky-table", "sm-sticky-table--first-column"):
            if token not in table_source:
                errors.append(f"{contract.table_template}: classe obrigatória ausente: {token}")
    html_files = _html_files()
    protected_pages = {page for page, _table in LIST_TEMPLATE_CONTRACTS.values()} | {
        contract.page_template for contract in OPERATIONAL_GRID_CONTRACTS
    }
    shell_sources = {"templates/page_shell_base.html", "templates/list_page_base.html"}
    for relative_path in html_files - MANUAL_SHELL_ALLOWLIST - protected_pages - shell_sources:
        source = _read(relative_path)
        if _has_class(source, "page-header") or _has_class(source, "main-content"):
            errors.append(f"Shell manual não registrado: {relative_path}")
    for relative_path in html_files:
        source = _read(relative_path)
        for class_name in OBSOLETE_LAYOUT_CLASSES:
            if _has_class(source, class_name):
                errors.append(f"Classe de layout obsoleta em {relative_path}: {class_name}")
        errors.extend(_check_tabs_contract(relative_path, source))
    canonical_tabs_source = _read(CANONICAL_TABS_TEMPLATE)
    if not _has_class(canonical_tabs_source, "sm-tabs"):
        errors.append(f"Componente canônico de abas sem sm-tabs: {CANONICAL_TABS_TEMPLATE}")
    for attribute in ("data-sm-list-tabs", "data-sm-tab-id"):
        if not _attribute_values(canonical_tabs_source, attribute):
            errors.append(f"Componente canônico de abas sem {attribute}: {CANONICAL_TABS_TEMPLATE}")
    primary_tables = {table for _page, table in LIST_TEMPLATE_CONTRACTS.values()} | {
        contract.table_template for contract in OPERATIONAL_GRID_CONTRACTS
    }
    table_files = {path for path in html_files if "<table" in _read(path)}
    for relative_path in sorted(table_files - primary_tables - SECONDARY_TABLE_ALLOWLIST):
        errors.append(f"Tabela sem contrato ou exceção registrada: {relative_path}")
    if (PROJECT_ROOT / "static" / "css" / "school-manager.css").exists():
        errors.append("CSS customizado duplicado em static/css/school-manager.css")
    if "school-manager.css' %}?v=" in _read("templates/base.html"):
        errors.append("Versionamento manual do CSS ainda está ativo em base.html")
    return sorted(set(errors))


def _check_scroll_contract(relative_path: str, source: str) -> list[str]:
    errors = []
    for token in ("table-responsive", "sm-scroll-region", 'tabindex="0"'):
        if token not in source:
            errors.append(f"{relative_path}: contrato de rolagem ausente: {token}")
    if "aria-label=" not in source and "aria-labelledby=" not in source:
        errors.append(f"{relative_path}: região rolável sem nome acessível")
    return errors


def _has_class(source: str, class_name: str) -> bool:
    return any(class_name in value.split() for value in _attribute_values(source, "class"))


def _attribute_values(source: str, attribute_name: str) -> list[str]:
    pattern = re.compile(
        rf"(?<![-:\w]){re.escape(attribute_name)}\s*=\s*"
        r'(?:"([^"]*)"|\'([^\']*)\'|([^\s>"\'/]+))',
        flags=re.IGNORECASE,
    )
    return [
        next(value for value in match.groups() if value is not None)
        for match in pattern.finditer(source)
    ]


def _check_tabs_contract(relative_path: str, source: str) -> list[str]:
    """Bloqueia APIs de abas fora do partial canônico sem falsos positivos."""
    if relative_path == CANONICAL_TABS_TEMPLATE or relative_path.startswith(
        DURALUX_REFERENCE_PREFIX
    ):
        return []
    class_tokens = {
        token.casefold() for value in _attribute_values(source, "class") for token in value.split()
    }
    violations = [name for name in ("nav-tabs", "nav-pills", "tab-pane") if name in class_tokens]
    if any(value.casefold() == "tab" for value in _attribute_values(source, "role")):
        violations.append("role=tab")
    if any(
        value.casefold() in {"tab", "pill"} for value in _attribute_values(source, "data-bs-toggle")
    ):
        violations.append("data-bs-toggle=tab|pill")
    return [f"Abas fora do componente canônico em {relative_path}: {token}" for token in violations]
