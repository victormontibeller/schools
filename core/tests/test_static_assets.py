"""Testes de integridade do conjunto curado de assets estáticos."""

import json
import re
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command

from base.staticfiles import SchoolManagerManifestStaticFilesStorage

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


def test_school_manager_css_comes_from_design_system() -> None:
    expected = (
        Path(settings.BASE_DIR)
        / "design_system"
        / "refs"
        / "duralux"
        / "css"
        / "school-manager.css"
    )

    assert Path(finders.find("css/school-manager.css")) == expected


def test_static_url_is_simple_in_development() -> None:
    assert staticfiles_storage.url("css/school-manager.css") == "/static/css/school-manager.css"


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


def test_collectstatic_generates_hashed_manifest(settings, tmp_path) -> None:
    settings.DEBUG = False
    settings.STATIC_ROOT = tmp_path

    call_command("collectstatic", interactive=False, verbosity=0)

    manifest = json.loads((tmp_path / "staticfiles.json").read_text(encoding="utf-8"))
    hashed_name = manifest["paths"]["css/school-manager.css"]

    assert re.fullmatch(r"css/school-manager\.[0-9a-f]{12}\.css", hashed_name)
    assert (tmp_path / hashed_name).is_file()

    storage = SchoolManagerManifestStaticFilesStorage(
        location=tmp_path,
        base_url="/static/",
    )
    assert storage.url("css/school-manager.css") == f"/static/{hashed_name}"
