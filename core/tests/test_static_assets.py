"""Testes de integridade do conjunto curado de assets estáticos."""

import re
from pathlib import Path

from django.contrib.staticfiles import finders

PRODUCTION_ASSETS = (
    "css/bootstrap.min.css",
    "css/vendors.min.css",
    "css/theme.min.css",
    "css/landing.css",
    "css/school-manager.css",
    "js/vendors.min.js",
    "js/common-init.min.js",
    "js/landing.js",
    "js/htmx.min.js",
)


def test_templates_production_assets_are_discoverable() -> None:
    assert all(finders.find(asset) for asset in PRODUCTION_ASSETS)


def test_curated_css_local_urls_resolve() -> None:
    for asset in PRODUCTION_ASSETS:
        if not asset.endswith(".css"):
            continue
        path = Path(finders.find(asset))
        references = re.findall(r"url\(([^)]+)\)", path.read_text(errors="ignore"))
        for reference in references:
            relative = reference.strip(" \"'").split("?", 1)[0].split("#", 1)[0]
            if not relative or relative.startswith(("data:", "http:", "https:")):
                continue
            assert (path.parent / relative).resolve().is_file(), f"{asset}: {reference}"
