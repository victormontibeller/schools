"""Formulários de salas físicas."""

import json

from django import forms
from django.core.exceptions import ValidationError

from rooms.models import Room


class RoomForm(forms.ModelForm):
    """Formulário ModelForm para criação/edição de salas.

    Expõe `resources` (JSONField) como textarea para o usuário digitar
    um objeto JSON de recursos (ex.: {\"projetor\": true, \"ar_condicionado\": true}).
    """

    class Meta:
        model = Room
        fields = ["name", "code", "capacity", "type", "floor", "building", "resources"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "type": forms.Select(attrs={"class": "form-select"}),
            "floor": forms.TextInput(attrs={"class": "form-control"}),
            "building": forms.TextInput(attrs={"class": "form-control"}),
            "resources": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": '{"projetor": true}'}
            ),
        }
        labels = {
            "name": "Nome",
            "code": "Código",
            "capacity": "Capacidade",
            "type": "Tipo",
            "floor": "Andar",
            "building": "Prédio",
            "resources": "Recursos (JSON)",
        }
        help_texts = {
            "resources": 'Objeto JSON. Ex.: {"projetor": true, "ar_condicionado": true}.',
        }

    def clean_resources(self) -> dict:
        """Converte o texto JSON em dict, validando o formato."""
        value = self.cleaned_data.get("resources")
        if value in (None, "", {}):
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"JSON inválido em Recursos: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValidationError("Recursos deve ser um objeto JSON.")
            return parsed
        return value
