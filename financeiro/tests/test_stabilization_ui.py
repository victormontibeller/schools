"""Navegação e persistência financeiras com HTMX e sem JavaScript."""

import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect

from base.tests.factories import StudentFactory
from core.tests.ui.test_canonical_layouts import _authenticate
from financeiro.models import BillingEntry
from financeiro.tests.test_stabilization import _renegotiated_payment


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("javascript_enabled", [True, False])
def test_overdue_pagination_and_reversal_work_with_and_without_javascript(
    browser, client, user, live_server, javascript_enabled
):
    for _ in range(23):
        BillingEntry.objects.create(
            student=StudentFactory(),
            description="UI overdue",
            principal_value=10,
            due_date=timezone.localdate() - dt.timedelta(days=1),
        )
    _original, payment, _successor = _renegotiated_payment(user)
    browser_context = browser.new_context(java_script_enabled=javascript_enabled)
    page = browser_context.new_page()
    try:
        _authenticate(page, client, user, live_server)
        page.goto(live_server.url + reverse("finance_overdue_report"))
        rows = page.locator("#overdue-details tbody tr")
        expect(rows).to_have_count(20)
        if javascript_enabled:
            page.locator("#school-navigation").evaluate(
                "node => node.dataset.persistenceMarker = 'preserved'"
            )
        page.get_by_role("link", name="Próxima página").click()
        expect(rows).to_have_count(3)
        expect(page).to_have_url(live_server.url + reverse("finance_overdue_report") + "?page=2")
        if javascript_enabled:
            expect(page.locator("#school-navigation")).to_have_attribute(
                "data-persistence-marker", "preserved"
            )
        page.get_by_role("link", name="Página anterior").click()
        expect(rows).to_have_count(20)

        page.goto(live_server.url + reverse("payment_reverse", args=[payment.pk]))
        due_date = timezone.localdate() + dt.timedelta(days=7)
        date_field = page.locator('[name="adjustment_due_date"]')
        expect(date_field).to_have_value(timezone.localdate().isoformat())
        date_field.fill(due_date.isoformat())
        page.locator('[name="reason"]').fill("Ajuste solicitado")
        with page.expect_request(lambda request: request.method == "POST") as posted:
            page.get_by_role("button", name="Salvar", exact=True).click()
        assert posted.value.headers.get("origin") == live_server.url
        expect(page).to_have_url(live_server.url + reverse("payment_queue"))
        payment.refresh_from_db()
        assert payment.status == "REVERSED"
        assert BillingEntry.objects.get(reversal_allocation__payment=payment).due_date == due_date
    finally:
        browser_context.close()
