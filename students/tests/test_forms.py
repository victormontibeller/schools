"""Testes dos campos obrigatórios de alunos."""

import pytest

from students.forms import StudentEditForm


@pytest.mark.django_db
def test_student_edit_requires_all_profile_fields():
    form = StudentEditForm(data={})

    assert not form.is_valid()
    for field_name in StudentEditForm.Meta.fields:
        if field_name != "photo":
            assert field_name in form.errors
