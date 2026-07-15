"""Formulários de grade horária e horários."""

from django import forms

from agenda.contracts import TimeSlot
from rooms.contracts import Room
from teachers.contracts import Subject, Teacher


class ScheduleForm(forms.Form):
    """Formulário para criar item da grade horária (a turma vem da URL)."""

    teacher = forms.ModelChoiceField(
        label="Professor",
        queryset=Teacher.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    subject = forms.ModelChoiceField(
        label="Disciplina",
        queryset=Subject.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    time_slot = forms.ModelChoiceField(
        label="Horário",
        queryset=TimeSlot.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    room = forms.ModelChoiceField(
        label="Sala",
        queryset=Room.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    valid_from = forms.DateField(
        label="Válido a partir de",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    valid_until = forms.DateField(
        label="Válido até",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )


class TimeSlotForm(forms.ModelForm):
    """Formulário de cadastro de faixa de horário recorrente."""

    class Meta:
        model = TimeSlot
        fields = ["day_of_week", "slot_number", "start_time", "end_time"]
        widgets = {
            "day_of_week": forms.Select(attrs={"class": "form-select"}),
            "slot_number": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        }
        labels = {
            "day_of_week": "Dia da Semana",
            "slot_number": "Nº do Horário",
            "start_time": "Início",
            "end_time": "Fim",
        }
