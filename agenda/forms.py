"""Formulários de período e células da matriz de horários."""

from __future__ import annotations

from django import forms

from agenda.models import TimeSlot


class TimeSlotForm(forms.ModelForm):
    """Configura um período de turno, reutilizável por todos os dias letivos."""

    version = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = TimeSlot
        fields = ["slot_number", "shift", "start_time", "end_time", "version"]
        widgets = {
            "slot_number": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "shift": forms.Select(attrs={"class": "form-select"}),
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "version": forms.HiddenInput(),
        }
        labels = {
            "slot_number": "Nº do período",
            "shift": "Turno",
            "start_time": "Início",
            "end_time": "Fim",
        }


class ScheduleCellForm(forms.Form):
    """Valida campos da célula; regras de disponibilidade pertencem ao service."""

    teacher_id = forms.ChoiceField(
        label="Professor", widget=forms.Select(attrs={"class": "form-select form-select-sm"})
    )
    subject_id = forms.ChoiceField(
        label="Disciplina", widget=forms.Select(attrs={"class": "form-select form-select-sm"})
    )
    room_id = forms.ChoiceField(
        label="Sala",
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    valid_from = forms.DateField(
        label="Válido a partir de",
        widget=forms.DateInput(attrs={"class": "form-control form-control-sm", "type": "date"}),
    )
    valid_until = forms.DateField(
        label="Válido até",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control form-control-sm", "type": "date"}),
    )
    version = forms.IntegerField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, choices: dict[str, tuple[tuple[str, str], ...]], **kwargs) -> None:
        """Recebe choices da view, que os obteve por selector público."""
        super().__init__(*args, **kwargs)
        self.fields["teacher_id"].choices = choices["teachers"]
        self.fields["subject_id"].choices = choices["subjects"]
        self.fields["room_id"].choices = choices["rooms"]


class ScheduleEndForm(forms.Form):
    """Valida a semana a partir da qual a célula deixa de vigorar."""

    valid_until = forms.DateField(
        label="Encerrar a partir de",
        widget=forms.DateInput(attrs={"class": "form-control form-control-sm", "type": "date"}),
    )
    version = forms.IntegerField(widget=forms.HiddenInput())


class ScheduleCopyDayForm(forms.Form):
    """Valida o dia de origem, destino e referência para cópia atômica."""

    source_day = forms.ChoiceField(
        label="Copiar de", widget=forms.Select(attrs={"class": "form-select"})
    )
    target_day = forms.ChoiceField(
        label="Para", widget=forms.Select(attrs={"class": "form-select"})
    )
    as_of = forms.DateField(
        label="Vigente em", widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )

    def __init__(self, *args, day_choices=(), **kwargs) -> None:
        """Recebe os dias letivos canônicos do selector/view."""
        super().__init__(*args, **kwargs)
        self.fields["source_day"].choices = day_choices
        self.fields["target_day"].choices = day_choices
