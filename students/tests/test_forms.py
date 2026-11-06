"""Testes dos campos obrigatórios de alunos."""

import pytest
from django.template.loader import render_to_string

from students.forms import StudentEditForm


@pytest.mark.django_db
def test_student_edit_requires_identification_without_child_digital_contact():
    form = StudentEditForm(data={})

    assert not form.is_valid()
    for field_name in [
        "enrollment_number",
        "first_name",
        "last_name",
        "birth_date",
    ]:
        assert field_name in form.errors
    for field_name in [
        "observations",
        "gender",
        "blood_type",
        "cpf",
        "rg_number",
        "phone_mobile",
        "email",
        "photo",
    ]:
        assert field_name not in form.errors


def test_student_edit_allows_later_contact_completion_without_account_or_alert_preferences():
    form = StudentEditForm()
    assert "observations" in form.fields
    assert not form.fields["email"].widget.attrs.get("readonly")
    assert (
        not {"user", "accepts_email_notifications", "accepts_whatsapp_notifications"}
        & form.fields.keys()
    )


def test_student_edit_renders_fields_without_inline_checkbox_configuration():
    rendered = render_to_string(
        "partials/person_form_fields.html",
        {"form": StudentEditForm(), "exclude_field": "photo"},
    )

    assert 'name="first_name"' in rendered
    assert 'name="email"' in rendered
    assert "Observações" in rendered
