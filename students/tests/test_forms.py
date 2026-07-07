"""Testes dos campos obrigatórios de alunos."""

import pytest

from students.forms import StudentEditForm


@pytest.mark.django_db
def test_student_edit_requires_model_required_fields_only():
    form = StudentEditForm(data={})

    assert not form.is_valid()
    for field_name in ["enrollment_number", "first_name", "last_name", "birth_date", "gender"]:
        assert field_name in form.errors
    for field_name in [
        "blood_type",
        "nationality",
        "cpf",
        "rg_number",
        "rg_issuer",
        "rg_state",
        "phone_mobile",
        "email",
        "special_needs",
        "photo",
    ]:
        assert field_name not in form.errors
