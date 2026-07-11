"""Testes do contrato público da landing page."""

import html as html_lib
import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse


def _response_html(response) -> str:
    """Decodifica o HTML da resposta para asserções de apresentação."""
    return response.content.decode(response.charset or "utf-8")


def _visible_text(markup: str) -> str:
    """Normaliza o conteúdo textual, ignorando a marcação HTML."""
    without_tags = re.sub(r"<[^>]+>", " ", markup)
    return " ".join(html_lib.unescape(without_tags).split())


def test_render_succeeds_for_anonymous_visitor(client):
    """Visitantes anônimos recebem a landing semântica e seu hero principal."""
    response = client.get(reverse("index"))
    markup = _response_html(response)

    assert response.status_code == 200
    assert response.templates[0].name == "landing.html"
    assert len(re.findall(r"<h1(?:\s[^>]*)?>", markup, flags=re.IGNORECASE)) == 1
    assert "Centralize a operação escolar e veja o que precisa de atenção hoje." in markup
    assert '<a class="skip-link" href="#main-content">' in markup
    assert '<main id="main-content">' in markup
    assert (
        'aria-label="Exemplo do painel operacional mostrando indicadores, '
        'pendências e agenda escolar"' in markup
    )


@pytest.mark.django_db
def test_redirect_succeeds_for_authenticated_user(client, user):
    """Usuários autenticados seguem direto para o painel canônico da escola."""
    client.force_login(user)

    response = client.get(reverse("index"))

    assert response.status_code == 302
    assert response.url == reverse("dashboard")


def test_render_exposes_expected_conversion_paths(client):
    """CTAs direcionam demonstrações, clientes e redes aos fluxos corretos."""
    response = client.get(reverse("index"))
    markup = _response_html(response)
    demo_url = reverse("demo_signup")
    login_url = reverse("login")
    plans = list(response.context["plans"])

    assert markup.count(f'href="{demo_url}"') >= 5
    assert f'href="{login_url}">Entrar</a>' in markup
    assert 'href="#produto"' in markup
    assert "Ver o produto em ação" in markup
    assert [plan["cta_url"] for plan in plans[:2]] == ["demo_signup", "demo_signup"]
    assert plans[2]["cta_href"].startswith("mailto:")
    assert f'href="{plans[2]["cta_href"]}"' in markup


def test_render_uses_only_supported_public_claims(client):
    """A landing oferece sete dias sem anunciar integrações ainda indisponíveis."""
    response = client.get(reverse("index"))
    text = _visible_text(_response_html(response)).casefold()

    assert "7 dias" in text
    assert "sete dias" in text
    assert "importação de alunos via csv" in text
    assert "14 dias" not in text
    assert "whatsapp" not in text
    assert re.search(r"\bsso\b", text) is None
    assert re.search(r"\bldap\b", text) is None
    assert re.search(r"\bsla\b", text) is None


def test_render_exposes_accessible_faq(client):
    """Cada pergunta controla e identifica explicitamente sua resposta."""
    response = client.get(reverse("index"))
    markup = _response_html(response)
    faq_count = len(response.context["faqs"])
    controls = re.findall(r'aria-controls="(faq-\d+)"', markup)
    labelled_by = re.findall(r'aria-labelledby="(faq-heading-\d+)"', markup)

    expected_panels = {f"faq-{index}" for index in range(1, faq_count + 1)}
    expected_headings = {f"faq-heading-{index}" for index in range(1, faq_count + 1)}

    assert faq_count > 0
    assert set(controls) == expected_panels
    assert set(labelled_by) == expected_headings
    assert markup.count('data-bs-parent="#faq-accordion"') == faq_count
    for panel_id in expected_panels:
        assert f'id="{panel_id}"' in markup
    for heading_id in expected_headings:
        assert f'id="{heading_id}"' in markup


def test_render_loads_only_local_assets(client, settings):
    """Folhas de estilo e scripts da landing são servidos pelos assets locais."""
    response = client.get(reverse("index"))
    markup = _response_html(response)
    stylesheet_urls = re.findall(
        r'<link\b(?=[^>]*\brel="stylesheet")[^>]*\bhref="([^"]+)"',
        markup,
        flags=re.IGNORECASE,
    )
    script_urls = re.findall(
        r'<script\b[^>]*\bsrc="([^"]+)"',
        markup,
        flags=re.IGNORECASE,
    )
    asset_urls = stylesheet_urls + script_urls

    assert asset_urls
    assert any(url.startswith(f"{settings.STATIC_URL}css/landing.css") for url in asset_urls)
    assert any(url.startswith(f"{settings.STATIC_URL}js/landing.js") for url in asset_urls)
    assert all(url.startswith(settings.STATIC_URL) for url in asset_urls)
    for url in asset_urls:
        asset_path = url.removeprefix(settings.STATIC_URL).partition("?")[0]
        assert finders.find(asset_path) is not None


def test_public_assets_support_progressive_and_reduced_motion():
    """Conteúdo permanece visível sem Observer e movimento reduzido desliga efeitos."""
    script_path = finders.find("js/landing.js")
    stylesheet_path = finders.find("css/landing.css")

    assert script_path is not None
    assert stylesheet_path is not None

    script = Path(script_path).read_text(encoding="utf-8")
    stylesheet = Path(stylesheet_path).read_text(encoding="utf-8")

    assert '!("IntersectionObserver" in window)' in script
    assert "showAllRevealElements();" in script
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in script
    assert "@media (prefers-reduced-motion: reduce)" in stylesheet
