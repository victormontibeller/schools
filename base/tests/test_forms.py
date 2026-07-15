"""Testes dos helpers compartilhados de formulários."""

from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.forms import NON_FIELD_ERRORS
from django.test import RequestFactory

from base.exceptions import ValidationError
from base.forms import apply_validation_errors, submitted_form_data


class ExampleForm(forms.Form):
    """Formulário mínimo usado para validar o mapeamento de erros."""

    name = forms.CharField(required=False)


def test_apply_validation_errors_maps_known_field() -> None:
    form = ExampleForm({})
    form.is_valid()

    apply_validation_errors(form, ValidationError(errors={"name": ["Nome inválido."]}))

    assert form.errors["name"] == ["Nome inválido."]


def test_apply_validation_errors_maps_global_and_unknown_fields_to_form() -> None:
    form = ExampleForm({})
    form.is_valid()

    apply_validation_errors(
        form,
        ValidationError(
            errors={
                "__all__": ["Combinação inválida."],
                "removed_field": ["Campo não disponível."],
            }
        ),
    )

    assert form.errors[NON_FIELD_ERRORS] == [
        "Combinação inválida.",
        "Campo não disponível.",
    ]


def test_submitted_form_data_keeps_only_post_and_file_fields() -> None:
    upload = SimpleUploadedFile("avatar.png", b"image")
    request = RequestFactory().post("/", {"name": "Ana", "avatar": upload})

    result = submitted_form_data(
        {"name": "Ana", "avatar": request.FILES["avatar"], "role": "ADMIN"},
        request,
    )

    assert result == {"name": "Ana", "avatar": request.FILES["avatar"]}
