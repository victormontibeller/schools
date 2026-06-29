"""Formulário de salas físicas."""

from django import forms

from rooms.models import Room


class RoomForm(forms.ModelForm):
    """Formulário ModelForm para criação/edição de salas."""

    class Meta:
        model = Room
        fields = [
            "name",
            "code",
            "capacity",
            "type",
            "floor",
            "building",
        ]
        labels = {
            "name": "Nome",
            "code": "Código",
            "capacity": "Capacidade",
            "type": "Tipo",
            "floor": "Andar",
            "building": "Prédio",
        }
