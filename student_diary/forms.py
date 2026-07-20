"""Formulários da Agenda escolar."""

from django import forms

from base.forms import VersionedModelForm
from classes.contracts import Class
from student_diary.models import DiaryCategory, DiaryOption


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

    def __init__(
        self,
        *args,
        categories,
        available_category_ids,
        initial_payload=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        initial_payload = initial_payload or {}
        answers = initial_payload.get("answers", {})
        available_category_ids = {str(category_id) for category_id in available_category_ids}
        self.routine_fields = []
        self.meal_fields = []
        for category in categories:
            field_name = f"answer_{category.pk}"
            selected_option = str(answers.get(str(category.pk), "") or "")
            is_available = str(category.pk) in available_category_ids
            choices = [
                (
                    str(option.pk),
                    option.label if option.is_enabled else f"{option.label} (indisponível)",
                )
                for option in category.options.all()
                if (is_available and option.is_enabled) or str(option.pk) == selected_option
            ]
            if not (is_available and category.is_required):
                choices.insert(0, ("", "Sem resposta"))
            self.fields[field_name] = forms.ChoiceField(
                label=category.name,
                choices=choices,
                required=is_available and category.is_required,
                widget=forms.RadioSelect(attrs={"class": "form-check-input sm-diary-choice-input"}),
            )
            self.initial[field_name] = selected_option
            target = (
                self.meal_fields
                if category.section == DiaryCategory.Section.MEAL
                else self.routine_fields
            )
            target.append(self._choice_cell(field_name))
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
            "notes": self.cleaned_data.get("notes", ""),
        }


class RoutineAspectForm(VersionedModelForm):
    """Cria e edita os dados configuráveis de um item da Agenda."""

    class Meta:
        model = DiaryCategory
        fields = [
            "name",
            "section",
            "display_order",
            "is_required",
            "applies_morning",
            "applies_afternoon",
            "applies_full",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "section": forms.Select(attrs={"class": "form-select"}),
            "display_order": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "applies_morning": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "applies_afternoon": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "applies_full": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "name": "Nome",
            "section": "Seção",
            "display_order": "Ordem",
            "is_required": "Resposta obrigatória",
            "applies_morning": "Manhã",
            "applies_afternoon": "Tarde",
            "applies_full": "Integral",
        }


class RoutineAspectToggleForm(VersionedModelForm):
    """Altera reversivelmente a disponibilidade de um item."""

    class Meta:
        model = DiaryCategory
        fields = ["is_enabled"]
        widgets = {"is_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"})}
        labels = {"is_enabled": "Ativo na Agenda"}


class RoutineOptionForm(VersionedModelForm):
    """Cria e edita uma opção de resposta do item."""

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
        labels = {"is_enabled": "Disponível na Agenda"}


class DiaryReviewForm(forms.Form):
    """Coleta somente o motivo textual de uma devolução."""

    feedback = forms.CharField(
        label="Motivo da devolução",
        max_length=1000,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
