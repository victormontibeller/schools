"""Formulários do módulo de calendário acadêmico."""

from django import forms

from academic_calendar.models import AcademicYear, CalendarEvent


class AcademicYearForm(forms.ModelForm):
    """Formulário ModelForm para criação de ano letivo."""

    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "end_date", "status"]
        labels = {
            "name": "Nome",
            "start_date": "Início",
            "end_date": "Término",
            "status": "Situação",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class EventForm(forms.ModelForm):
    """Formulário ModelForm para criação/edição de evento."""

    class Meta:
        model = CalendarEvent
        fields = [
            "title",
            "description",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "type",
            "audience",
            "class_obj",
            "academic_year",
            "is_public",
        ]
        labels = {
            "title": "Título",
            "description": "Descrição",
            "start_date": "Início",
            "end_date": "Término",
            "start_time": "Hora de início (opcional)",
            "end_time": "Hora de término (opcional)",
            "type": "Tipo",
            "audience": "Público-alvo",
            "class_obj": "Turma",
            "academic_year": "Ano Letivo",
            "is_public": "Público para responsáveis/alunos",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class HolidayForm(forms.ModelForm):
    """Formulário ModelForm para criação de feriado."""

    class Meta:
        from academic_calendar.models import Holiday

        model = Holiday
        fields = ["name", "date", "type", "is_recurring"]
        labels = {
            "name": "Nome",
            "date": "Data",
            "type": "Tipo",
            "is_recurring": "Repete todo ano",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }
