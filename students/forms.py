"""Formulários de alunos."""

import json

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError

from students.models import Student


class StudentForm(forms.ModelForm):
    """Formulário de cadastro e edição de aluno."""

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
            "nationality",
            "cpf",
            "rg_number",
            "rg_issuer",
            "rg_state",
            "phone_mobile",
            "email",
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
            "nationality": forms.TextInput(attrs={"class": "form-control"}),
            "cpf": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "000.000.000-00"}
            ),
            "rg_number": forms.TextInput(attrs={"class": "form-control"}),
            "rg_issuer": forms.TextInput(attrs={"class": "form-control", "placeholder": "SSP"}),
            "rg_state": forms.Select(attrs={"class": "form-select"}),
            "phone_mobile": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "(00) 00000-0000"}
            ),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
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
            "nationality": "Nacionalidade",
            "cpf": "CPF",
            "rg_number": "RG — Número",
            "rg_issuer": "RG — Órgão Emissor",
            "rg_state": "RG — UF",
            "phone_mobile": "Celular",
            "email": "E-mail do Aluno",
            "special_needs": "Necessidades Especiais (JSON)",
            "photo": "Foto",
        }
        help_texts = {
            "special_needs": 'Objeto JSON. Ex.: {"medica": ["asma"], "acessibilidade": []}.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from locations.selectors import StateSelector

        self.fields["rg_state"].choices = StateSelector().list_choices(include_blank=True)

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
                raise DjangoValidationError(
                    f"JSON inválido em Necessidades Especiais: {exc}"
                ) from exc
            if not isinstance(parsed, dict):
                raise DjangoValidationError("Necessidades Especiais deve ser um objeto JSON.")
            return parsed
        return value


class StudentEditForm(StudentForm):
    """Formulário de edição das informações exibidas no perfil do aluno."""

    class Meta(StudentForm.Meta):
        fields = [
            "enrollment_number",
            "first_name",
            "last_name",
            "birth_date",
            "gender",
            "blood_type",
            "nationality",
            "cpf",
            "rg_number",
            "rg_issuer",
            "rg_state",
            "phone_mobile",
            "email",
            "special_needs",
            "photo",
        ]
        widgets = {
            **StudentForm.Meta.widgets,
            "photo": forms.ClearableFileInput(attrs={"class": "sm-profile-avatar-input"}),
        }
