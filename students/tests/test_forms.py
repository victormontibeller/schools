"""Testes dos campos obrigatórios de alunos."""

import pytest

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
