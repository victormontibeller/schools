"""Testes dos campos obrigatórios de responsáveis."""

import pytest

from guardians.forms import GuardianEditForm


@pytest.mark.django_db
def test_guardian_edit_requires_relationship_type_only():
    form = GuardianEditForm(data={})

    assert not form.is_valid()
    assert "relationship_type" in form.errors
    for field_name in set(form.fields) - {"relationship_type"}:
        assert field_name not in form.errors
