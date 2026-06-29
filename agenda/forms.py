"""Formulários de grade horária e horários."""

from django import forms

from agenda.models import TimeSlot
from rooms.models import Room
from teachers.models import Subject, Teacher


class ScheduleForm(forms.Form):
    """Formulário para criar item da grade horária (a turma vem da URL)."""

    teacher = forms.ModelChoiceField(label="Professor", queryset=Teacher.objects.all())
    subject = forms.ModelChoiceField(label="Disciplina", queryset=Subject.objects.all())
    time_slot = forms.ModelChoiceField(label="Horário", queryset=TimeSlot.objects.all())
    room = forms.ModelChoiceField(label="Sala", queryset=Room.objects.all(), required=False)
    valid_from = forms.DateField(
        label="Válido a partir de", widget=forms.DateInput(attrs={"type": "date"})
    )
    valid_until = forms.DateField(
        label="Válido até (opcional)",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )


class TimeSlotForm(forms.ModelForm):
    """Formulário de cadastro de faixa de horário recorrente."""

    class Meta:
        model = TimeSlot
        fields = ["day_of_week", "slot_number", "start_time", "end_time"]
        labels = {
            "day_of_week": "Dia da Semana",
            "slot_number": "Nº do Horário",
            "start_time": "Início",
            "end_time": "Fim",
        }
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }
