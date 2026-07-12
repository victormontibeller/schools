"""Formulários de salas físicas."""

from django import forms

from rooms.models import Room


class RoomForm(forms.ModelForm):
    """Formulário ModelForm para criação/edição de salas.

    Expõe observações em texto livre, sem exigir conhecimento de JSON.
    """

    class Meta:
        model = Room
        fields = ["name", "code", "capacity", "type", "floor", "building", "observations"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "type": forms.Select(attrs={"class": "form-select"}),
            "floor": forms.TextInput(attrs={"class": "form-control"}),
            "building": forms.TextInput(attrs={"class": "form-control"}),
            "observations": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
        labels = {
            "name": "Nome",
            "code": "Código",
            "capacity": "Capacidade",
            "type": "Tipo",
            "floor": "Andar",
            "building": "Prédio",
            "observations": "Observações",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True
        self.fields["observations"].required = False
