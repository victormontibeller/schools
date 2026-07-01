"""Formulários de turmas e matrículas."""

from django import forms

from classes.models import Class


class ClassForm(forms.ModelForm):
    """Formulário ModelForm para criação/edição de turmas."""

    class Meta:
        model = Class
        fields = ["name", "grade", "shift", "academic_year", "max_students", "class_teacher"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "grade": forms.TextInput(attrs={"class": "form-control"}),
            "shift": forms.Select(attrs={"class": "form-select"}),
            "academic_year": forms.NumberInput(
                attrs={"class": "form-control", "min": 2000, "max": 2100}
            ),
            "max_students": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "class_teacher": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "name": "Nome",
            "grade": "Série",
            "shift": "Turno",
            "academic_year": "Ano Letivo",
            "max_students": "Vagas",
            "class_teacher": "Professor Responsável",
        }


class EnrollmentForm(forms.Form):
    """Formulário para matricular aluno em turma (via ID)."""

    student_id = forms.UUIDField(
        label="ID do aluno",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    class_obj_id = forms.UUIDField(
        label="ID da turma",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
