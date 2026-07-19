"""Formulários da Agenda escolar."""

from django import forms

from base.forms import VersionedModelForm
from classes.contracts import Class
from student_diary.models import DiaryCategory, DiaryMeal, DiaryOption


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
                "rows": 6,
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
            selected_option = str(answers.get(str(category.pk), "") or "")
            choices = [
                (
                    str(option.pk),
                    option.label if option.is_enabled else f"{option.label} (indisponível)",
                )
                for option in category.options.all()
                if (category.is_enabled and option.is_enabled) or str(option.pk) == selected_option
            ]
            if not (category.is_enabled and category.is_required):
                choices.insert(0, ("", "Sem resposta"))
            self.fields[field_name] = forms.ChoiceField(
                label=category.name,
                choices=choices,
                required=category.is_enabled and category.is_required,
                widget=forms.RadioSelect(attrs={"class": "form-check-input sm-diary-choice-input"}),
            )
            self.initial[field_name] = selected_option
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


class RoutineAspectForm(VersionedModelForm):
    """Cria e edita os dados configuráveis de um aspecto."""

    class Meta:
        model = DiaryCategory
        fields = ["name", "display_order", "is_required"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "display_order": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "name": "Nome",
            "display_order": "Ordem",
            "is_required": "Resposta obrigatória",
        }


class RoutineAspectToggleForm(VersionedModelForm):
    """Altera reversivelmente a disponibilidade de um aspecto."""

    class Meta:
        model = DiaryCategory
        fields = ["is_enabled"]
        widgets = {"is_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"})}
        labels = {"is_enabled": "Ativo na rotina"}


class RoutineOptionForm(VersionedModelForm):
    """Cria e edita uma opção de resposta do aspecto."""

    class Meta:
        model = DiaryOption
        fields = ["label", "display_order"]
        widgets = {
            "label": forms.TextInput(attrs={"class": "form-control"}),
            "display_order": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
        }
        labels = {"label": "Opção", "display_order": "Ordem"}


class RoutineOptionToggleForm(VersionedModelForm):
    """Altera reversivelmente a disponibilidade de uma opção."""

    class Meta:
        model = DiaryOption
        fields = ["is_enabled"]
        widgets = {"is_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"})}
        labels = {"is_enabled": "Disponível na rotina"}


class DiaryReviewForm(forms.Form):
    """Coleta somente o motivo textual de uma devolução."""

    feedback = forms.CharField(
        label="Motivo da devolução",
        max_length=1000,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
