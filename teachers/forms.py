from django import forms

from teachers.models import Subject


class SubjectForm(forms.ModelForm):
    """Formulário de cadastro de disciplina."""

    class Meta:
        model = Subject
        fields = ["name", "code", "workload"]
        labels = {"name": "Nome", "code": "Código", "workload": "Carga Horária (h/ano)"}


class TeacherForm(forms.Form):
    """Formulário de criação de professor a partir de usuário existente."""

    user_id = forms.UUIDField(label="Usuário (ID)")
    registration_number = forms.CharField(max_length=30, label="Matrícula")
    hire_date = forms.DateField(
        required=False, label="Data de Admissão", widget=forms.DateInput(attrs={"type": "date"})
    )
