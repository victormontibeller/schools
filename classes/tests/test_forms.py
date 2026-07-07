"""Testes dos campos obrigatórios de turmas."""

import pytest

from classes.forms import ClassForm


@pytest.mark.django_db
def test_class_form_requires_every_field():
    form = ClassForm(data={})

    assert not form.is_valid()
    for field_name in form.fields:
        assert field_name in form.errors
