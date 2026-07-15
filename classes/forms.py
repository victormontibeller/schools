"""Formulários de turmas e matrículas."""

import json

from django import forms

from base.forms import VersionedModelForm
from classes.models import GRADES_BY_EDUCATION_STAGE, Class


class ClassForm(VersionedModelForm):
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
        for field_name, field in self.fields.items():
            if field_name != "version":
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
