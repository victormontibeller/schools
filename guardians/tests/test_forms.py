"""Testes dos campos obrigatórios de responsáveis."""

import pytest

from guardians.forms import GuardianContactEditForm


@pytest.mark.django_db
def test_guardian_edit_requires_all_personal_fields_except_optional_avatar():
    form = GuardianContactEditForm(data={})

    assert not form.is_valid()
    for field_name in set(form.fields) - {
        "avatar",
        "accepts_email_notifications",
        "accepts_whatsapp_notifications",
    }:
        assert field_name in form.errors


@pytest.mark.django_db
def test_guardian_contact_edit_uses_three_columns_on_desktop():
    form = GuardianContactEditForm()

    assert form.fields["first_name"].widget.attrs["data_grid"] == "col-12 col-sm-4"
    assert form.fields["phone_mobile"].widget.attrs["data_grid"] == "col-12 col-sm-4"
