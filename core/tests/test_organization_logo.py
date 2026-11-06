"""Upload e prévia local dos logotipos de organizações."""

import base64
from io import BytesIO
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from PIL import Image
from playwright.sync_api import expect

from core.forms import BusinessUnitForm, SchoolEditForm
from core.models import BusinessUnit
from core.tests.test_business_unit_views import _unit_payload
from tenancy.models import School


def _png(color="red", size=(3, 3)):
    stream = BytesIO()
    Image.new("RGB", size, color).save(stream, format="PNG")
    return stream.getvalue()


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["school", "unit"])
@pytest.mark.parametrize("htmx", [False, True])
def test_save_logo_persists_upload(client, user, settings, tmp_path, kind, htmx):
    settings.MEDIA_ROOT = tmp_path
    client.force_login(user)
    if kind == "school":
        organization = School.objects.create(schema_name="logo_test", name="Escola")
        url = "/app/escola/editar/"
    else:
        organization = BusinessUnit.objects.create(name="Unidade")
        url = f"/app/empresas/{organization.pk}/editar/"
    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    detail = client.get(url.removesuffix("editar/"))
    assert f'href="{url}"'.encode() in detail.content
    form_response = client.get(url, **headers)
    assert b"data-image-picker" in form_response.content
    assert b'method="post"' in form_response.content
    assert b'enctype="multipart/form-data"' in form_response.content
    if htmx:
        assert f'action="{url}"'.encode() in form_response.content
    payload = _unit_payload(logo=SimpleUploadedFile("logo.png", _png(), "image/png"))
    response = client.post(url, payload, **headers)
    assert response.status_code == (200 if htmx else 302)
    organization.refresh_from_db()
    with organization.logo.open("rb") as uploaded:
        image = Image.open(uploaded)
        assert image.format == "WEBP"
        assert image.getpixel((0, 0)) == (255, 0, 0)
    saved_name = organization.logo.name
    # Abrir e cancelar a edição não altera a imagem persistida.
    client.get(url, **headers)
    client.get(url.removesuffix("editar/"), **headers)
    organization.refresh_from_db()
    assert organization.logo.name == saved_name


@pytest.mark.ui
@pytest.mark.parametrize("form_class", [SchoolEditForm, BusinessUnitForm])
@pytest.mark.parametrize("existing", [False, True])
def test_preview_logo_handles_selection_and_errors(page, form_class, existing):
    original = "data:image/png;base64," + base64.b64encode(_png("blue", size=(18, 3))).decode()
    markup = render_to_string(
        "partials/organization_form_fields.html",
        {
            "form": form_class(),
            "organization": SimpleNamespace(
                name="Escola", logo=SimpleNamespace(url=original) if existing else None
            ),
        },
    )
    page.set_content(markup)
    page.add_style_tag(
        path=str(settings.BASE_DIR / "design_system/refs/duralux/css/school-manager.css")
    )
    page.add_script_tag(path=str(settings.BASE_DIR / "static/js/sm-image-picker.js"))
    picker = page.locator("[data-image-picker]")
    field = picker.locator('input[type="file"]')
    status = picker.get_by_role("status")
    preview = picker.locator("label img")
    if existing:
        expect(preview).to_have_css("object-fit", "contain")
    file = {"name": "logo.png", "mimeType": "image/png", "buffer": _png(size=(18, 3))}
    field.set_input_files(file)
    expect(status).to_have_text("Prévia — clique em Salvar para confirmar")
    expect(preview).to_have_css("object-fit", "contain")
    expect(preview).to_have_attribute("alt", "Prévia da imagem selecionada")
    selected = preview.get_attribute("src")
    field.dispatch_event("cancel")
    expect(preview).to_have_attribute("src", selected)
    field.set_input_files({"name": "bad.png", "mimeType": "image/png", "buffer": b"bad"})
    expect(status).to_contain_text("Não foi possível gerar a prévia")
    if existing:
        expect(preview).to_have_attribute("src", original)
    else:
        expect(picker.locator("label .avatar-text")).to_have_text("E")
    # Simula o novo fragmento inserido por HTMX sem recarregar o script.
    page.locator("body").evaluate("(body, html) => body.innerHTML = html", markup)
    field.set_input_files(file)
    expect(status).to_have_text("Prévia — clique em Salvar para confirmar")
    expect(preview).to_have_css("object-fit", "contain")


@pytest.mark.ui
def test_preview_logo_ignores_old_reads(page):
    page.set_content(
        render_to_string(
            "partials/organization_form_fields.html",
            {"form": SchoolEditForm(), "organization": SimpleNamespace(name="Escola")},
        )
    )
    page.evaluate("""() => {
        window.readers = [];
        window.FileReader = class {
            constructor() { window.readers.push(this); }
            readAsDataURL() {}
        };
    }""")
    page.add_script_tag(path=str(settings.BASE_DIR / "static/js/sm-image-picker.js"))
    field = page.locator('input[name="logo"]')
    for color in ("red", "blue"):
        field.set_input_files(
            {"name": color + ".png", "mimeType": "image/png", "buffer": _png(color)}
        )
    blue = "data:image/png;base64," + base64.b64encode(_png("blue")).decode()
    page.evaluate(
        """src => {
        readers[1].result = src;
        readers[1].onload();
    }""",
        blue,
    )
    preview = page.locator("[data-image-picker] label img")
    expect(preview).to_have_attribute("src", blue)
    page.evaluate("() => { readers[0].result = 'data:invalid'; readers[0].onload(); }")
    expect(preview).to_have_attribute("src", blue)
    expect(page.get_by_role("status")).to_have_text("Prévia — clique em Salvar para confirmar")


@pytest.mark.ui
@pytest.mark.parametrize("field_name", ["avatar", "photo"])
@pytest.mark.parametrize("existing", [False, True])
def test_preview_person_image_is_shared_accessible_and_delegated(page, field_name, existing):
    from django import forms

    from base.forms import ImageUploadField

    class PersonForm(forms.Form):
        avatar = ImageUploadField(required=False)
        photo = ImageUploadField(required=False)

    markup = render_to_string(
        "partials/person_profile_hero.html",
        {
            "profile_avatar_field": PersonForm()[field_name],
            "profile_has_image": existing,
            "profile_image_url": "data:image/png;base64," + base64.b64encode(_png()).decode(),
            "profile_name": "Pessoa",
            "profile_initial": "P",
        },
    )
    page.set_content(markup)
    page.add_style_tag(
        path=str(settings.BASE_DIR / "design_system/refs/duralux/css/school-manager.css")
    )
    page.add_script_tag(path=str(settings.BASE_DIR / "static/js/sm-image-picker.js"))
    for _ in range(2):
        field = page.locator(f'input[name="{field_name}"]')
        field.set_input_files({"name": "person.png", "mimeType": "image/png", "buffer": _png()})
        expect(page.get_by_role("status")).to_have_text("Prévia — clique em Salvar para confirmar")
        expect(page.locator("label .visually-hidden")).to_have_text("Alterar foto de Pessoa")
        expect(page.locator("label img")).to_have_css("object-fit", "cover")
        field.dispatch_event("cancel")
        expect(page.locator("label img")).to_have_attribute("alt", "Prévia da imagem selecionada")
        page.locator("body").evaluate("(body, html) => body.innerHTML = html", markup)


@pytest.mark.ui
def test_preview_rejects_oversize_before_reading(page):
    page.set_content(
        render_to_string(
            "partials/organization_form_fields.html",
            {
                "form": SchoolEditForm(),
                "organization": SimpleNamespace(name="Escola"),
            },
        )
    )
    page.evaluate(
        "() => { window.FileReader = class { constructor() { throw Error('must not read'); } }; }"
    )
    page.add_script_tag(path=str(settings.BASE_DIR / "static/js/sm-image-picker.js"))
    page.locator('input[name="logo"]').set_input_files(
        {"name": "large.png", "mimeType": "image/png", "buffer": b"x" * (5 * 1024 * 1024 + 1)}
    )
    expect(page.get_by_role("status")).to_contain_text("até 5 MiB")
