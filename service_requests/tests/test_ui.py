"""Jornada privada com HTML nativo, HTMX e telas pequenas."""

import time

import pytest
from django.test import Client
from django.urls import reverse
from playwright.sync_api import expect

from base.tests.images import png_upload
from core.tests.ui.test_canonical_layouts import _authenticate
from service_requests.models import ServiceRequest


def _wait_for_stable_response_button(page):
    """Observa fim da rolagem nativa; timers de página não rodam com JS desabilitado."""
    previous, stable, deadline = None, 0, time.monotonic() + 5
    while time.monotonic() < deadline:
        measured = page.evaluate("""() => {
            const button = [...document.querySelectorAll('button')]
                .find(b => b.textContent.trim() === 'Enviar mensagem');
            const rect = button.getBoundingClientRect();
            return {geometry: [document.scrollingElement.scrollTop, rect.x, rect.y,
                rect.width, rect.height], animating: document.getAnimations()
                .some(a => a.playState === 'running')};
        }""")
        stable = stable + 1 if measured["geometry"] == previous else 0
        if stable >= 3 and not measured["animating"]:
            return
        previous = measured["geometry"]
        time.sleep(0.05)
    pytest.fail("Rolagem e geometria do botão não estabilizaram")


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("javascript_enabled", [True, False])
@pytest.mark.parametrize("viewport", [(1280, 720), (1280, 480), (390, 844)])
def test_family_opens_staff_answers_and_family_reopens(
    browser, live_server, setup_requests, javascript_enabled, viewport, tmp_path
):
    contexts = []

    def signed_in_page(account):
        context = browser.new_context(
            java_script_enabled=javascript_enabled,
            viewport={"width": viewport[0], "height": viewport[1]},
        )
        contexts.append(context)
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        # Personas possuem sessões independentes. Trocar cookies numa página com polling
        # deixa respostas antigas competirem com a nova identidade no navegador.
        _authenticate(page, Client(), account, live_server)
        page.bring_to_front()
        return page

    try:
        family_page = signed_in_page(setup_requests["family"])
        family_page.goto(live_server.url + reverse("service_request_create"))
        family_page.get_by_label("Assunto", exact=False).fill("Atendimento no navegador")
        family_page.get_by_label("Mensagem", exact=False).fill("Mensagem privada inicial")
        family_page.get_by_label("Anexo PDF ou imagem", exact=False).set_input_files(
            {"name": "anexo.png", "mimeType": "image/png", "buffer": png_upload().read()}
        )
        family_page.get_by_role("button", name="Salvar", exact=True).click()
        expect(family_page.get_by_text("Primeira resposta até", exact=False)).to_be_visible()
        expect(family_page.get_by_text("Contato fictício: 0000-0000", exact=True)).to_be_visible()
        ticket = ServiceRequest.objects.get(subject="Atendimento no navegador")
        with family_page.expect_download() as downloaded:
            family_page.get_by_role("link", name="Baixar anexo privado 1", exact=True).click()
        assert downloaded.value.failure() is None
        assert family_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        staff_page = signed_in_page(setup_requests["staff"])
        staff_page.goto(live_server.url + reverse("service_request_detail", args=[ticket.pk]))
        staff_page.get_by_label("Mensagem", exact=False).fill("Resposta humana do setor")
        staff_page.mouse.move(viewport[0] * 0.7, viewport[1] * 0.75)
        staff_page.mouse.wheel(0, 500)
        _wait_for_stable_response_button(staff_page)
        staff_page.get_by_role("button", name="Enviar mensagem", exact=True).click()
        expect(
            staff_page.get_by_text("Aguardando resposta da família.", exact=True)
        ).to_be_visible()
        staff_page.get_by_label("Alterar estado", exact=True).select_option("RESOLVED")
        staff_page.get_by_role("button", name="Atualizar estado", exact=True).click()
        expect(staff_page.get_by_text("Solicitação resolvida.", exact=False)).to_be_visible()
        family_page.bring_to_front()
        family_page.goto(live_server.url + reverse("service_request_detail", args=[ticket.pk]))
        family_page.get_by_role("button", name="Reabrir e iniciar novo prazo", exact=True).click()
        expect(family_page.get_by_text("Primeira resposta até", exact=False)).to_be_visible()
        ticket.refresh_from_db()
        assert ticket.cycle == 2 and ticket.first_response_at is None
        assert family_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        for index, context in enumerate(contexts):
            context.tracing.stop(path=tmp_path / f"request-journey-{index}.zip")
            context.close()
