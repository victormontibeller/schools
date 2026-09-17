"""Dimensões compactas da identidade da escola com imagem carregada."""

from io import BytesIO

import pytest
from PIL import Image
from playwright.sync_api import expect

from core.tests.ui.test_canonical_layouts import _authenticate
from tenancy.models import School


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("viewport", [(1280, 720), (1280, 480), (390, 844)])
def test_school_brand_stays_compact_with_portrait_logo(page, client, user, live_server, viewport):
    School.objects.create(
        schema_name="compact_brand", name="Colégio Horizonte Paulista", logo="demo/logo.png"
    )
    buffer = BytesIO()
    Image.new("RGB", (120, 300), "blue").save(buffer, format="PNG")
    page.route(
        "**/media/**",
        lambda route: route.fulfill(content_type="image/png", body=buffer.getvalue()),
    )
    page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
    _authenticate(page, client, user, live_server)
    for path in ("/app/escola/", "/app/"):
        page.goto(live_server.url + path)
        header = page.locator(".nxl-header")
        expect(header).to_be_visible()
        assert header.bounding_box()["height"] <= 82
        if viewport[0] >= 992:
            logo = page.locator(".header-school-logo")
            expect(logo).to_be_visible()
            assert logo.bounding_box()["height"] == 32
            assert logo.bounding_box()["width"] == 32
            assert page.locator(".header-school-brand").bounding_box()["height"] <= 48
        if path == "/app/escola/":
            logo = page.locator("#school-information-card .sm-organization-logo")
            expect(logo).to_be_visible()
            assert logo.bounding_box()["width"] == 64
            assert logo.bounding_box()["height"] == 64
            expect(logo).to_have_js_property("naturalWidth", 120)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
