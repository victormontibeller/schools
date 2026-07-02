"""Testes dos helpers de renderizacao de formularios."""

from django import forms

from core.templatetags.widget_utils import form_widget


class SampleForm(forms.Form):
    name = forms.CharField()
    category = forms.ChoiceField(choices=[("A", "Categoria A")])
    active = forms.BooleanField(required=False)


def test_form_widget_applies_control_class():
    rendered = form_widget(SampleForm()["name"])

    assert 'class="form-control"' in rendered


def test_form_widget_applies_select_class():
    rendered = form_widget(SampleForm()["category"])

    assert 'class="form-select"' in rendered


def test_form_widget_applies_checkbox_class():
    rendered = form_widget(SampleForm()["active"])

    assert 'class="form-check-input"' in rendered
