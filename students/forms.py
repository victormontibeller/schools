"""Formulários de alunos."""

from django import forms

from base.forms import ImageUploadField, VersionedModelForm
from students.models import Student


class StudentForm(VersionedModelForm):
    """Formulário de cadastro e edição de aluno."""

    photo = ImageUploadField(
        required=False,
        label="Foto",
        widget=forms.FileInput(attrs={"class": "sm-profile-avatar-input"}),
    )

    REQUIRED_FIELDS = ("first_name", "last_name", "birth_date")

    class Meta:
        model = Student
        fields = [
            "enrollment_number",
            "first_name",
            "last_name",
            "birth_date",
            "gender",
            "blood_type",
            "cpf",
            "rg_number",
            "phone_mobile",
            "email",
            "observations",
            "photo",
        ]
        widgets = {
            "enrollment_number": forms.TextInput(
                attrs={"class": "form-control", "readonly": True, "placeholder": "Gerada ao salvar"}
            ),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "birth_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "blood_type": forms.Select(attrs={"class": "form-select"}),
            "cpf": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "000.000.000-00"}
            ),
            "rg_number": forms.TextInput(attrs={"class": "form-control"}),
            "phone_mobile": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "(00) 00000-0000"}
            ),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "observations": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "maxlength": 250}
            ),
            "photo": forms.ClearableFileInput(attrs={"class": "sm-profile-avatar-input"}),
        }
        labels = {
            "enrollment_number": "Matrícula",
            "first_name": "Nome",
            "last_name": "Sobrenome",
            "birth_date": "Data de Nascimento",
            "gender": "Gênero",
            "blood_type": "Tipo Sanguíneo",
            "cpf": "CPF",
            "rg_number": "RG — Número",
            "phone_mobile": "Celular",
            "email": "E-mail do Aluno",
            "observations": "Observações",
            "photo": "Foto",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["gender"].required = False
        for field_name in self.REQUIRED_FIELDS:
            if field_name in self.fields:
                self.fields[field_name].required = True


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
            "cpf",
            "rg_number",
            "phone_mobile",
            "email",
            "observations",
            "photo",
        ]
        widgets = {
            **StudentForm.Meta.widgets,
            "photo": forms.ClearableFileInput(attrs={"class": "sm-profile-avatar-input"}),
        }
