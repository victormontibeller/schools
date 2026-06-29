"""Formulários de turmas e matrículas."""

from django import forms

from classes.models import Class


class ClassForm(forms.ModelForm):
    """Formulário ModelForm para criação/edição de turmas."""

    class Meta:
        model = Class
        fields = ["name", "grade", "shift", "academic_year", "max_students", "class_teacher"]
        labels = {
            "name": "Nome",
            "grade": "Série",
            "shift": "Turno",
            "academic_year": "Ano Letivo",
            "max_students": "Vagas",
            "class_teacher": "Professor Responsável",
        }
        widgets = {
            "academic_year": forms.NumberInput(attrs={"min": 2000, "max": 2100}),
        }


class EnrollmentForm(forms.Form):
    """Formulário para matricular aluno em turma (via ID)."""

    student_id = forms.UUIDField(label="ID do aluno")
    class_obj_id = forms.UUIDField(label="ID da turma")
