"""Testes dos campos obrigatórios de alunos."""

import pytest
from django.template.loader import render_to_string

from students.forms import StudentEditForm


@pytest.mark.django_db
def test_student_edit_requires_all_personal_fields_except_optional_groups():
    form = StudentEditForm(data={})

    assert not form.is_valid()
    for field_name in [
        "enrollment_number",
        "first_name",
        "last_name",
        "birth_date",
        "gender",
        "blood_type",
        "cpf",
        "rg_number",
        "phone_mobile",
        "email",
    ]:
        assert field_name in form.errors
    for field_name in [
        "observations",
        "photo",
    ]:
        assert field_name not in form.errors


def test_student_edit_keeps_email_readonly_and_includes_observations():
    form = StudentEditForm()

    assert "observations" in form.fields
    assert form.fields["email"].widget.attrs["readonly"] is True
    assert form.fields["accepts_email_notifications"].widget.attrs["data_grid"] == "col-12 col-md-6"
    assert (
        form.fields["accepts_whatsapp_notifications"].widget.attrs["data_grid"] == "col-12 col-md-6"
    )


def test_student_edit_renders_fields_without_inline_checkbox_configuration():
    rendered = render_to_string(
        "partials/person_form_fields.html",
        {"form": StudentEditForm(), "exclude_field": "photo"},
    )

    assert 'name="first_name"' in rendered
    assert 'name="email"' in rendered
    assert "Observações" in rendered
