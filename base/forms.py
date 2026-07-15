"""Contratos compartilhados para formulários de escrita."""

from django import forms


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
