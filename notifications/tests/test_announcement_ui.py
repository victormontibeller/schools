"""Jornada no Chromium com HTML nativo, HTMX e viewports do contrato."""

from unittest.mock import patch

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from core.tests.ui.test_canonical_layouts import _authenticate
from notifications.models import Announcement
from notifications.tests.test_announcement_workflow import family


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("javascript_enabled", [True, False])
@pytest.mark.parametrize("viewport", [(1280, 720), (1280, 480), (390, 844)])
def test_author_and_family_complete_publication_and_acknowledgement(
    browser,
    client,
    user,
    school,
    live_server,
    javascript_enabled,
    viewport,
):
    account, _, _, _ = family(user)
    context = browser.new_context(
        java_script_enabled=javascript_enabled,
        viewport={"width": viewport[0], "height": viewport[1]},
    )
    page = context.new_page()
    try:
        with patch("notifications.outbox_services.publish_task_after_commit"):
            _authenticate(page, client, user, live_server)
            page.goto(live_server.url + reverse("announcement_create"))
            page.get_by_label("Título", exact=False).fill("Comunicado do navegador")
            page.get_by_label("Mensagem", exact=False).fill("Texto privado no sistema")
            page.get_by_label("Destinatários", exact=False).select_option("FAMILIES")
            page.get_by_label("Solicitar ciência explícita", exact=True).check()
            page.get_by_role("button", name="Salvar", exact=True).click()
            expect(page.get_by_role("button", name="Publicar agora")).to_be_visible()
            page.get_by_role("button", name="Publicar agora").click()
            expect(page.get_by_text("Comunicado publicado.", exact=False)).to_be_visible()
            draft = Announcement.objects.get(title="Comunicado do navegador")
            assert draft.revisions.count() == 1
            page.goto(live_server.url + reverse("announcement_list"))
            expect(page.get_by_role("link", name="Comunicado do navegador")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            _authenticate(page, client, account, live_server)
            page.goto(live_server.url + reverse("announcement_detail", args=[draft.pk]))
            page.get_by_role("button", name="Estou ciente", exact=True).click()
            expect(page.get_by_text("Ciência registrada em", exact=False)).to_be_visible()
            assert draft.revisions.get().recipients.get().acknowledged_at
    finally:
        context.close()
