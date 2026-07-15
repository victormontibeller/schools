"""Testes dos formulários institucionais compartilhados."""

from core.forms import BusinessUnitForm, SchoolEditForm


def test_organization_forms_share_fields_and_preserve_labels() -> None:
    business_unit_form = BusinessUnitForm()
    school_form = SchoolEditForm()

    assert list(business_unit_form.fields) == list(school_form.fields)
    assert business_unit_form.fields["name"].label == "Nome da Empresa"
    assert school_form.fields["name"].label == "Nome da Escola"


def test_organization_forms_require_every_field_except_logo() -> None:
    for form in (BusinessUnitForm(), SchoolEditForm()):
        assert form.fields["logo"].required is False
        assert all(field.required for name, field in form.fields.items() if name != "logo")
