"""Contratos e helpers compartilhados para formulários de escrita."""

from django import forms
from django.http import HttpRequest

from base.exceptions import ValidationError


def apply_validation_errors(form: forms.Form, error: ValidationError) -> None:
    """Adiciona erros de domínio aos campos válidos ou ao formulário."""
    for field, messages in error.errors.items():
        target = field if field != "__all__" and field in form.fields else None
        for message in messages:
            form.add_error(target, message)


def submitted_form_data(cleaned_data: dict[str, object], request: HttpRequest) -> dict[str, object]:
    """Retorna somente dados limpos cujos campos foram enviados no request."""
    submitted = set(request.POST) | set(request.FILES)
    return {key: value for key, value in cleaned_data.items() if key in submitted}


class VersionedModelForm(forms.ModelForm):
    """Inclui a versão original e detecta edição iniciada sobre dados obsoletos."""

    version = forms.IntegerField(required=False, min_value=0, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and not self.instance._state.adding:
            self.fields["version"].required = True
            self.fields["version"].initial = self.instance.version

    def clean(self):
        cleaned_data = super().clean()
        if self.instance and not self.instance._state.adding:
            submitted_version = cleaned_data.get("version")
            if submitted_version is not None and submitted_version != self.instance.version:
                raise forms.ValidationError(
                    "Este registro foi alterado por outra pessoa. Recarregue os dados."
                )
        return cleaned_data
