"""Testes dos campos obrigatórios de responsáveis."""

import pytest

from guardians.forms import GuardianEditForm


@pytest.mark.django_db
def test_guardian_edit_requires_all_profile_fields_except_avatar():
    form = GuardianEditForm(data={})

    assert not form.is_valid()
    for field_name in form.fields:
        if field_name != "avatar":
            assert field_name in form.errors
