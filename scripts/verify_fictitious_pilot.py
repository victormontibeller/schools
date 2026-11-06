"""Homologação HTTP/Chromium local com segredos somente no arquivo privado do ensaio."""

import json
import os
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
CURRENT_PHASE = "initialization"


def write_private(path, data):
    descriptor = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def captured_url(folder, recipient, fragment):
    for path in sorted(folder.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        message = json.loads(path.read_text())
        if message["recipient"] == recipient:
            for url in re.findall(r"https?://[^\s<>]+", message["body"]):
                if fragment in url:
                    return url
    raise RuntimeError("capture_missing")


def login(page, base, credential):
    response = page.goto(base + "login/")
    if response.status != 200:
        raise RuntimeError("login_unavailable")
    page.locator('[name="email"]').fill(credential["email"])
    page.locator('[name="password"]').fill(credential["password"])
    page.locator("form").filter(has=page.locator('[name="email"]')).locator(
        'button[type="submit"]'
    ).click()
    page.wait_for_url(base + "app/")


def main():
    global CURRENT_PHASE
    import django

    django.setup()
    from django.urls import reverse
    from playwright.sync_api import sync_playwright

    from accounts.selectors import AccountSelector
    from accounts.staff_services import StaffAccountService
    from base.context import tenant_schema_context
    from core.fictitious import require_fictitious
    from notifications.outbox_selectors import OutboxSelector
    from notifications.outbox_services import OutboxService

    root = require_fictitious(schema="public")
    access_path = root / "access.json"
    access = json.loads(access_path.read_text())
    school = access["schools"]["piloto"]
    base = school["url"]
    evidence = school["evidence"]
    with tenant_schema_context("piloto"):
        if "ACTIVATION_CHECK" not in school["credentials"]:
            administrator = AccountSelector().get_by_id(school["credentials"]["ADMIN"]["id"])
            invited = StaffAccountService(user=administrator).create_staff_user(
                {
                    "first_name": "Ativação",
                    "last_name": "Fictícia",
                    "email": "activation-check@example.test",
                    "role_name": "SECRETARY",
                }
            )
            school["credentials"]["ACTIVATION_CHECK"] = {
                "id": str(invited.pk),
                "email": invited.email,
                "password": secrets.token_urlsafe(24),
                "pending": True,
            }
            for delivery_id in list(OutboxSelector.pending_ids(limit=1000)):
                OutboxService().dispatch(delivery_id)
            write_private(access_path, access)
    checks = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(java_script_enabled=False)
        page = context.new_page()
        invited = school["credentials"]["ACTIVATION_CHECK"]
        if invited.get("pending"):
            page.goto(captured_url(root / "messages", invited["email"], "/convite-equipe/"))
            page.locator('[name="password"]').fill(invited["password"])
            page.locator('[name="password_confirm"]').fill(invited["password"])
            page.get_by_role("button", name="Definir senha e ativar", exact=True).click()
            page.wait_for_url(base + "login/")
            invited["pending"] = False
            write_private(access_path, access)
            checks.append("activation_native_form")
        else:
            checks.append("activation_completed_in_previous_run")
        CURRENT_PHASE = "recovery_request"
        page.goto(base + "password-reset/")
        page.locator('[name="email"]').fill(school["credentials"]["G1"]["email"])
        page.locator("form").filter(has=page.locator('[name="email"]')).locator(
            'button[type="submit"]'
        ).click()
        page.wait_for_url(base + "password-reset/done/")
        CURRENT_PHASE = "recovery_confirm"
        page.goto(
            captured_url(
                root / "messages", school["credentials"]["G1"]["email"], "/password-reset/confirm/"
            )
        )
        replacement = secrets.token_urlsafe(24)
        page.locator('[name="new_password1"]').fill(replacement)
        page.locator('[name="new_password2"]').fill(replacement)
        page.get_by_role("button", name="Confirmar", exact=True).click()
        page.wait_for_url(base + "password-reset/complete/")
        school["credentials"]["G1"]["password"] = replacement
        write_private(access_path, access)
        checks.append("recovery_native_form_local_smtp_capture")
        context.close()
        for key, credential in school["credentials"].items():
            CURRENT_PHASE = f"profile_{key}"
            context = browser.new_context(java_script_enabled=False)
            page = context.new_page()
            login(page, base, credential)
            if "Ambiente fictício" not in page.content():
                raise RuntimeError("fictitious_banner_missing")
            response = page.goto(base.rstrip("/") + reverse("announcement_list"))
            if response.status != 200:
                raise RuntimeError("announcement_list_unavailable")
            if key in {"G1", "G2"}:
                response = page.goto(
                    base.rstrip("/") + reverse("service_request_detail", args=[evidence["request"]])
                )
                if (key == "G1" and response.status != 200) or (
                    key == "G2" and response.status not in {403, 404}
                ):
                    raise RuntimeError("request_privacy_failed")
            if key == "FINANCE":
                response = context.request.get(
                    base.rstrip("/")
                    + reverse("payment_receipt_pdf", args=[evidence["payment_reversed"]])
                )
                # Reversed payment remains historical; receipt is available according to canonical policy.
                if response.status != 200 or not response.body().startswith(b"%PDF"):
                    raise RuntimeError("receipt_access_failed")
            if key in {"G1", "G2", "TEACHER1", "TEACHER2"}:
                response = page.goto(base + "users/novo/")
                if response.status not in {403, 404}:
                    raise RuntimeError("forbidden_action_available")
            checks.append(f"profile_{key.lower()}_login_navigation_no_javascript")
            context.close()
        CURRENT_PHASE = "tenant_isolation"
        other = access["schools"]["piloto_comparacao"]
        context = browser.new_context(java_script_enabled=False)
        page = context.new_page()
        login(page, other["url"], other["credentials"]["ADMIN"])
        response = page.goto(
            other["url"].rstrip("/")
            + reverse("announcement_detail", args=[evidence["announcement"]])
        )
        if response.status not in {403, 404}:
            raise RuntimeError("tenant_isolation_failed")
        checks.append("second_school_cannot_read_first_school")
        context.close()
        browser.close()
    write_private(
        root / "browser-proof.json",
        {
            "environment": "fictitious",
            "checks": checks,
            "actual_external_email": False,
            "javascript": False,
        },
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Browser exceptions often embed token-bearing URLs: never log their message/traceback.
        sys.exit(
            f"Homologação não concluída ({CURRENT_PHASE}, {type(error).__name__}); confira o cenário local."
        )
