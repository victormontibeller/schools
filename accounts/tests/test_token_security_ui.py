"""Formulários públicos com tokens preservam CSRF sem expor caminho no Referer."""

from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from playwright.sync_api import expect

from accounts.recovery_tokens import recovery_token_generator
from accounts.services import AccountService
from core.models import CustomUser, Role
from guardians.invitation_services import GuardianInvitationService
from guardians.models import Guardian
from teachers.models import Teacher

PASSWORD = "CoralHorizon842"


def _token_form(flow, actor):
    import datetime as dt

    from guardians.models import StudentGuardian
    from notifications.models import MessageLog
    from students.models import Student
    from tenancy.models import School

    School.objects.get_or_create(schema_name="test_school", defaults={"name": "Fictícia"})
    if flow == "guardian":
        Role.objects.get_or_create(name=Role.Name.GUARDIAN)
        guardian = Guardian.objects.create(
            first_name="Família", last_name="Teste", email="browser-guardian@test.local"
        )
        student = Student.objects.create(
            first_name="Criança",
            last_name="Fictícia",
            birth_date=dt.date(2022, 1, 1),
            enrollment_number="BROWSER-CHILD",
        )
        StudentGuardian.objects.create(student=student, guardian=guardian, has_custody=True)
        with patch("notifications.outbox_services.publish_task_after_commit"):
            account = GuardianInvitationService(user=actor).send_invitation(guardian.pk)
        token = MessageLog.objects.get(source_type="account_invitation", recipient=account).payload[
            "scope"
        ]["invitation_token"]
        path = reverse("guardian_invitation") + "?" + urlencode({"token": token})
    else:
        account = CustomUser.objects.create_user(
            email=f"browser-{flow}@test.local",
            password="PreviousPass842" if flow == "reset" else None,
            is_active=flow == "reset",
        )
        if flow == "teacher":
            account.role = Role.objects.get_or_create(name="TEACHER")[0]
            account.save()
            Teacher.objects.create(user=account, registration_number="BROWSER-INVITE")
            with patch("notifications.outbox_services.publish_task_after_commit"):
                token = AccountService().create_teacher_invitation_token(account.pk)
            path = reverse("teacher_invitation", args=[token])
        else:
            from tenancy.models import School

            School.objects.get_or_create(schema_name="test_school", defaults={"name": "Fictícia"})
            token = recovery_token_generator.make_token(account)
            path = reverse(
                "password_reset_confirm",
                args=[urlsafe_base64_encode(force_bytes(account.pk)), token],
            )
    return account, token, path


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("flow", ["teacher", "guardian", "reset"])
def test_token_form_submits_without_javascript_and_only_refers_origin(
    browser, user, live_server, flow
):
    account, token, path = _token_form(flow, user)
    browser_context = browser.new_context(java_script_enabled=False)
    page = browser_context.new_page()
    requests = []
    page.on("request", lambda request: requests.append(request))
    try:
        response = page.goto(live_server.url + path)
        assert response.status == 200
        token_page_url = page.url
        assert response.headers["referrer-policy"] == "strict-origin"
        assert response.headers["cache-control"] == "no-store"
        fields = (
            ("new_password1", "new_password2")
            if flow == "reset"
            else (
                "password",
                "password_confirm",
            )
        )
        for name in fields:
            page.locator(f'[name="{name}"]').fill(PASSWORD)
        button = "Confirmar" if flow == "reset" else "Definir senha e ativar"
        with page.expect_request(lambda request: request.method == "POST") as posted:
            page.get_by_role("button", name=button, exact=True).click()
        assert posted.value.headers["origin"] == live_server.url
        assert posted.value.headers["referer"] == live_server.url + "/"
        destination = "password_reset_complete" if flow == "reset" else "login"
        expect(page).to_have_url(live_server.url + reverse(destination))
        account.refresh_from_db()
        assert account.is_active
        assert account.check_password(PASSWORD)
        for request in requests:
            referrer = request.headers.get("referer", "")
            assert token not in referrer
            assert "?" not in referrer
            assert not referrer.startswith(token_page_url)
    finally:
        browser_context.close()


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_demo_verification_redirect_and_login_work_without_javascript(browser, live_server):
    captured = {}
    with patch("accounts.tasks.send_demo_verification_task.delay"):
        account = AccountService().create_demo_user(
            {
                "first_name": "Visitante",
                "last_name": "Demo",
                "email": "browser-demo@test.local",
                "password": PASSWORD,
            },
            lambda token: captured.setdefault("token", token),
        )
    token = captured["token"]
    verification_url = live_server.url + reverse("demo_verify", args=[token])
    browser_context = browser.new_context(java_script_enabled=False)
    page = browser_context.new_page()
    requests = []
    page.on("request", lambda request: requests.append(request))
    try:
        # DEMO confirms via GET and redirects; it has no token-bearing POST form.
        with page.expect_response(lambda response: response.url == verification_url) as verified:
            response = page.goto(verification_url)
        assert verified.value.status == 302
        assert verified.value.headers["referrer-policy"] == "strict-origin"
        assert verified.value.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "same-origin"
        expect(page).to_have_url(live_server.url + reverse("login"))
        account.refresh_from_db()
        assert account.is_active and account.email_verified_at
        page.locator('[name="email"]').fill(account.email)
        page.locator('[name="password"]').fill(PASSWORD)
        with page.expect_request(lambda request: request.method == "POST") as posted:
            page.locator('form button[type="submit"]').click()
        assert posted.value.headers["origin"] == live_server.url
        assert token not in posted.value.headers["referer"]
        expect(page).to_have_url(live_server.url + reverse("dashboard"))
        assert all(token not in request.headers.get("referer", "") for request in requests)
    finally:
        browser_context.close()
