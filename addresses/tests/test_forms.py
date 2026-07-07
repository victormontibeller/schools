"""Testes dos formularios do modulo de enderecos."""

import pytest


@pytest.mark.django_db
def test_address_form_loads_state_choices_from_database():
    from addresses.forms import AddressForm

    form = AddressForm()

    assert ("SP", "São Paulo (SP)") in form.fields["state"].choices
    assert ("RJ", "Rio de Janeiro (RJ)") in form.fields["state"].choices


@pytest.mark.django_db
def test_address_form_renders_state_options_in_html():
    from addresses.forms import AddressForm

    rendered = AddressForm()["state"].as_widget()

    assert '<option value="SP">São Paulo (SP)</option>' in rendered
    assert '<option value="RJ">Rio de Janeiro (RJ)</option>' in rendered


@pytest.mark.django_db
def test_address_form_filters_city_choices_by_selected_state():
    from addresses.forms import AddressForm

    form = AddressForm(initial={"state": "SP"})

    assert ("Campinas", "Campinas") in form.fields["city"].choices
    assert ("São Paulo", "São Paulo") in form.fields["city"].choices
    assert ("Niterói", "Niterói") not in form.fields["city"].choices


@pytest.mark.django_db
def test_address_form_disables_city_field_when_state_is_missing():
    from addresses.forms import AddressForm

    form = AddressForm()

    assert form.fields["city"].widget.attrs["disabled"] is True


@pytest.mark.django_db
def test_address_form_configures_postal_code_lookup_with_htmx():
    from addresses.forms import AddressForm

    form = AddressForm()
    attrs = form.fields["postal_code"].widget.attrs

    assert attrs["hx-get"] == "/addresses/postal-code-lookup/"
    assert attrs["hx-target"] == "#address-form-fields"
    assert attrs["hx-swap"] == "outerHTML"
    assert attrs["hx-include"] == "closest form"


@pytest.mark.django_db
def test_address_form_clears_invalid_city_from_instance(user):
    from addresses.forms import AddressForm
    from addresses.models import Address

    address = Address.objects.create(
        recipient="Secretaria",
        street="Rua Exemplo",
        number="10",
        complement="Sala 1",
        district="Centro",
        postal_code="01001000",
        state="AM",
        city="teste",
        created_by=user,
        updated_by=user,
    )

    form = AddressForm(instance=address)

    assert form.fields["state"].initial == ""
    assert form.fields["city"].initial == ""
    assert ("teste", "teste") not in form.fields["city"].choices
