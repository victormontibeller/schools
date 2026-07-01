"""Formulários de alunos."""

import json

from django import forms
from django.core.exceptions import ValidationError

from students.models import Student


class StudentForm(forms.ModelForm):
    """Formulário de cadastro e edição de aluno.

    Expõe todos os campos editáveis do modelo `Student`, incluindo o
    vínculo opcional com usuário (`user`) e necessidades especiais
    (`special_needs`), armazenadas como JSON.
    """

    class Meta:
        model = Student
        fields = [
            "user",
            "enrollment_number",
            "first_name",
            "last_name",
            "birth_date",
            "gender",
            "blood_type",
            "special_needs",
            "photo",
        ]
        widgets = {
            "user": forms.Select(attrs={"class": "form-select"}),
            "enrollment_number": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "birth_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "blood_type": forms.Select(attrs={"class": "form-select"}),
            "special_needs": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": '{"medical": ["asma"]}'}
            ),
            "photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
        labels = {
            "user": "Usuário do Sistema (opcional)",
            "enrollment_number": "Matrícula",
            "first_name": "Nome",
            "last_name": "Sobrenome",
            "birth_date": "Data de Nascimento",
            "gender": "Gênero",
            "blood_type": "Tipo Sanguíneo",
            "special_needs": "Necessidades Especiais (JSON)",
            "photo": "Foto",
        }
        help_texts = {
            "special_needs": 'Objeto JSON. Ex.: {"medica": ["asma"], "acessibilidade": []}.',
        }

    def clean_special_needs(self) -> dict:
        """Converte o texto JSON digitado em dict, validando o formato."""
        value = self.cleaned_data.get("special_needs")
        if value in (None, "", {}):
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"JSON inválido em Necessidades Especiais: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValidationError("Necessidades Especiais deve ser um objeto JSON.")
            return parsed
        return value
