"""Testes dos campos obrigatórios de responsáveis."""

import pytest

from guardians.forms import GuardianContactEditForm, GuardianEditForm


@pytest.mark.django_db
def test_guardian_edit_requires_all_personal_fields_except_optional_avatar():
    form = GuardianContactEditForm(data={})

    assert not form.is_valid()
    for field_name in set(form.fields) - {
        "avatar",
        "email",
        "accepts_email_notifications",
        "accepts_whatsapp_notifications",
    }:
        assert field_name in form.errors


@pytest.mark.django_db
def test_guardian_contact_edit_uses_three_columns_on_desktop():
    form = GuardianContactEditForm()

    assert form.fields["first_name"].widget.attrs["data_grid"] == "col-12 col-sm-4"
    assert form.fields["phone_mobile"].widget.attrs["data_grid"] == "col-12 col-sm-4"
    assert form.fields["accepts_email_notifications"].widget.attrs["data_grid"] == "col-12 col-md-6"
    assert (
        form.fields["accepts_whatsapp_notifications"].widget.attrs["data_grid"] == "col-12 col-md-6"
    )


@pytest.mark.django_db
def test_guardian_edit_disables_email_when_not_editable():
    form = GuardianEditForm(initial={"email": "responsavel@example.com"}, email_editable=False)

    assert form.fields["email"].disabled is True
