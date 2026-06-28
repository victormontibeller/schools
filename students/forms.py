from django import forms

from students.models import Student


class StudentForm(forms.ModelForm):
    """Formulário de cadastro e edição de aluno."""

    class Meta:
        model = Student
        fields = [
            "first_name",
            "last_name",
            "enrollment_number",
            "birth_date",
            "gender",
            "blood_type",
            "photo",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "first_name": "Nome",
            "last_name": "Sobrenome",
            "enrollment_number": "Matrícula",
            "birth_date": "Data de Nascimento",
            "gender": "Gênero",
            "blood_type": "Tipo Sanguíneo",
            "photo": "Foto",
        }
