"""Formulários da Agenda escolar."""

from django import forms

from classes.contracts import Class
from student_diary.models import DiaryCategory, DiaryMeal


class DiaryDailyFilterForm(forms.Form):
    """Filtros operacionais para carregar a Agenda de uma turma e data."""

    class_id = forms.ModelChoiceField(
        label="Turma",
        queryset=Class.objects.none(),
        widget=forms.Select(
            attrs={
                "class": "form-select form-select-sm",
                "aria-label": "Turma",
            }
        ),
    )
    date = forms.DateField(
        label="Data",
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "class": "form-control form-control-sm",
                "type": "date",
                "aria-label": "Data",
            },
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
        widget=forms.Textarea(
            attrs={
                "class": "form-control form-control-sm",
                "rows": 3,
                "data-diary-notes-input": "",
            }
        ),
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
                widget=forms.RadioSelect(attrs={"class": "form-check-input sm-diary-choice-input"}),
            )
            self.initial[field_name] = str(answers.get(str(category.pk), "") or "")
            self.aspect_fields.append(self._choice_cell(field_name))
        meal_labels = dict(DiaryMeal.MealType.choices)
        for meal_type in meal_types:
            field_name = f"meal_{meal_type}"
            self.fields[field_name] = forms.ChoiceField(
                label=meal_labels[meal_type],
                choices=DiaryMeal.Status.choices,
                widget=forms.RadioSelect(attrs={"class": "form-check-input sm-diary-choice-input"}),
            )
            self.initial[field_name] = meals.get(str(meal_type), "")
            self.meal_fields.append(self._choice_cell(field_name))
        self.initial["notes"] = initial_payload.get("notes", "")

    def _choice_cell(self, field_name: str) -> dict:
        """Monta os metadados de apresentação de um seletor inline."""
        bound_field = self[field_name]
        selected_value = str(bound_field.value() or "")
        choice_labels = {str(value): label for value, label in self.fields[field_name].choices}
        return {
            "field": bound_field,
            "label": bound_field.label,
            "selected_label": choice_labels.get(selected_value, "Selecionar"),
        }

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


class DiaryReviewForm(forms.Form):
    """Coleta somente o motivo textual de uma devolução."""

    feedback = forms.CharField(
        label="Motivo da devolução",
        max_length=1000,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
