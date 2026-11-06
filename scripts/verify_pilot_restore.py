"""Compara dados de negócio e valida leitura autenticada no restore fictício."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline")
    parser.add_argument("--output", required=True)
    options = parser.parse_args()
    import django

    django.setup()
    from django.urls import reverse
    from playwright.sync_api import sync_playwright

    from accounts.selectors import AccountSelector
    from base.context import tenant_schema_context
    from core.export_archive import json_bytes
    from core.export_selectors import FIELDS, SchoolExportSelector
    from core.fictitious import require_fictitious
    from scripts.verify_fictitious_pilot import login, write_private
    from service_requests.models import ServiceRequest

    root = require_fictitious(schema="public")
    state = json.loads((root / "access.json").read_text())
    result = {"schemas": {}, "checks": []}
    children = {}
    selector = SchoolExportSelector()
    for schema, school_data in state["schools"].items():
        with tenant_schema_context(schema):
            actor = AccountSelector().get_by_id(school_data["credentials"]["ADMIN"]["id"])
            school, _ = selector.authorized_school(actor)
            tables = {}
            for label in FIELDS:
                digest, count = hashlib.sha256(), 0
                for instance in selector.records(label, school):
                    digest.update(json_bytes(selector.serialize(instance, label)))
                    count += 1
                tables[label] = {"count": count, "sha256": digest.hexdigest()}
            result["schemas"][schema] = tables
            if schema == "piloto":
                children[schema] = str(
                    ServiceRequest.objects.get(pk=school_data["evidence"]["request"]).student_id
                )
    if options.baseline:
        baseline = json.loads(Path(options.baseline).read_text())
        if result["schemas"] != baseline["schemas"]:
            raise RuntimeError("business_fingerprint_mismatch")
        result["checks"].append("all_allowlisted_business_tables_match_source")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for profile in ("ADMIN", "G1"):
                school = state["schools"]["piloto"]
                context = browser.new_context(java_script_enabled=False)
                page = context.new_page()
                login(page, school["url"], school["credentials"][profile])
                paths = [
                    reverse("announcement_detail", args=[school["evidence"]["announcement"]]),
                    reverse("service_request_detail", args=[school["evidence"]["request"]]),
                    reverse("student_photo", args=[children["piloto"]]),
                ]
                for path in paths:
                    response = context.request.get(school["url"].rstrip("/") + path)
                    if response.status != 200:
                        raise RuntimeError("restored_authenticated_read_failed")
                result["checks"].append(f"restored_{profile.lower()}_login_content_private_media")
                context.close()
            browser.close()
        result["cache_isolated"] = os.environ.get("REDIS_URL", "").endswith("/2")
        if not result["cache_isolated"]:
            raise RuntimeError("restore_cache_not_isolated")
        result["reopening_authorized"] = False
        result["reconciliation_required"] = [
            "custody",
            "deactivation",
            "permissions",
            "payments",
            "documents",
        ]
    write_private(Path(options.output), result)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.exit(f"Validação não concluída ({type(error).__name__}); mantenha a escola fechada.")
