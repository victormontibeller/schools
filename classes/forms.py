"""Formulários de turmas e matrículas."""

import json

from django import forms

from classes.models import GRADES_BY_EDUCATION_STAGE, Class


class ClassForm(forms.ModelForm):
    """Formulário ModelForm para criação/edição de turmas."""

    class Meta:
        model = Class
        fields = [
            "name",
            "education_stage",
            "grade",
            "shift",
            "academic_year",
            "max_students",
            "class_teacher",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "grade": forms.Select(attrs={"class": "form-select"}),
            "education_stage": forms.Select(attrs={"class": "form-select"}),
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
            "education_stage": "Etapa de Ensino",
            "shift": "Turno",
            "academic_year": "Ano Letivo",
            "max_students": "Vagas",
            "class_teacher": "Professor Responsável",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True
        if not self.is_bound and self.instance._state.adding:
            self.fields["education_stage"].choices = [
                ("", "---------"),
                *Class.EducationStage.choices,
            ]
            self.initial["education_stage"] = ""
            self.initial["grade"] = ""
        grade_options = {
            stage: [{"value": grade, "label": Class.Grade(grade).label} for grade in grades]
            for stage, grades in GRADES_BY_EDUCATION_STAGE.items()
        }
        self.fields["education_stage"].widget.attrs["data-grade-stage"] = "true"
        self.fields["grade"].widget.attrs.update(
            {
                "data-grade-select": "true",
                "data-grade-options": json.dumps(grade_options, ensure_ascii=False),
            }
        )
        current_grade = getattr(self.instance, "grade", "") if self.instance else ""
        valid_grades = {choice.value for choice in Class.Grade}
        self.legacy_grade = (
            current_grade if current_grade and current_grade not in valid_grades else ""
        )
        if self.legacy_grade:
            self.fields["grade"].choices = [
                *self.fields["grade"].choices,
                (self.legacy_grade, f"Valor legado — {self.legacy_grade}"),
            ]


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
