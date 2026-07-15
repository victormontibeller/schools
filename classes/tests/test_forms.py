"""Testes dos campos obrigatórios de turmas."""

import pytest
from django import forms

from classes.forms import ClassForm
from classes.models import GRADES_BY_EDUCATION_STAGE, Class


@pytest.mark.django_db
def test_class_form_requires_every_field():
    form = ClassForm(data={})

    assert not form.is_valid()
    for field_name in set(form.fields) - {"version"}:
        assert field_name in form.errors


def test_class_form_renders_grade_as_structured_select():
    form = ClassForm()

    assert isinstance(form.fields["grade"].widget, forms.Select)
    assert form.fields["grade"].widget.attrs["data-grade-select"] == "true"
    assert form.fields["education_stage"].widget.attrs["data-grade-stage"] == "true"
    assert list(form.fields).index("education_stage") < list(form.fields).index("grade")
    assert form["education_stage"].value() == ""
    assert form["grade"].value() == ""


def test_grade_catalog_covers_every_option_once():
    configured = [grade for grades in GRADES_BY_EDUCATION_STAGE.values() for grade in grades]

    assert configured == list(Class.Grade)
    assert len(configured) == 19
