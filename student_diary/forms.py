"""Formulários da Agenda escolar."""

from django import forms

from classes.models import Class
from student_diary.models import DiaryCategory, DiaryMeal


class DiaryDailyFilterForm(forms.Form):
    """Filtros operacionais para carregar a Agenda de uma turma e data."""

    class_id = forms.ModelChoiceField(
        label="Turma",
        queryset=Class.objects.none(),
        widget=forms.Select(attrs={"class": "form-select", "data-grid": "col-md-6"}),
    )
    date = forms.DateField(
        label="Data",
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date", "data-grid": "col-md-4"}
        ),
    )

    def __init__(self, *args, classes, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_id"].queryset = classes


class DiaryStudentEntryForm(forms.Form):
    """Campos de rotina, alimentação e observação de uma criança."""

    notes = forms.CharField(
        label="Observações",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "data-grid": "col-12"}),
    )

    def __init__(self, *args, categories, meal_types, initial_payload=None, **kwargs):
        super().__init__(*args, **kwargs)
        initial_payload = initial_payload or {}
        answers = initial_payload.get("answers", {})
        meals = initial_payload.get("meals", {})
        self.aspect_fields = []
        self.meal_fields = []
        for category in categories:
            field_name = f"answer_{category.pk}"
            self.fields[field_name] = forms.ChoiceField(
                label=category.name,
                choices=[(str(option.pk), option.label) for option in category.options.all()],
                widget=forms.RadioSelect(attrs={"class": "sm-segmented-options"}),
            )
            self.initial[field_name] = str(answers.get(str(category.pk), "") or "")
            self.aspect_fields.append((category, self[field_name]))
        meal_labels = dict(DiaryMeal.MealType.choices)
        for meal_type in meal_types:
            field_name = f"meal_{meal_type}"
            self.fields[field_name] = forms.ChoiceField(
                label=meal_labels[meal_type],
                choices=DiaryMeal.Status.choices,
                widget=forms.RadioSelect(attrs={"class": "sm-segmented-options"}),
            )
            self.initial[field_name] = meals.get(str(meal_type), "")
            self.meal_fields.append((meal_type, self[field_name]))
        self.initial["notes"] = initial_payload.get("notes", "")

    def to_payload(self) -> dict:
        """Converte os campos validados no contrato do service."""
        return {
            "answers": {
                field_name.removeprefix("answer_"): value
                for field_name, value in self.cleaned_data.items()
                if field_name.startswith("answer_")
            },
            "meals": {
                field_name.removeprefix("meal_"): value
                for field_name, value in self.cleaned_data.items()
                if field_name.startswith("meal_")
            },
            "notes": self.cleaned_data.get("notes", ""),
        }


class RoutineAspectToggleForm(forms.ModelForm):
    """Formulário do único campo configurável de um aspecto fixo."""

    class Meta:
        model = DiaryCategory
        fields = ["is_enabled"]
        widgets = {"is_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"})}
        labels = {"is_enabled": "Ativo na rotina"}
