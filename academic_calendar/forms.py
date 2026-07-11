"""Formulários do módulo de calendário acadêmico."""

from django import forms

from academic_calendar.models import AcademicYear, CalendarEvent, Holiday


class AcademicYearForm(forms.ModelForm):
    """Formulário ModelForm para criação de ano letivo."""

    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "end_date", "status"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "name": "Nome",
            "start_date": "Início",
            "end_date": "Término",
            "status": "Situação",
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
            "type",
            "audience",
            "class_obj",
            "is_public",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "type": forms.Select(attrs={"class": "form-select"}),
            "audience": forms.Select(attrs={"class": "form-select"}),
            "class_obj": forms.Select(attrs={"class": "form-select"}),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "title": "Título",
            "description": "Descrição",
            "start_date": "Início",
            "end_date": "Término",
            "type": "Tipo",
            "audience": "Público-alvo",
            "class_obj": "Turma",
            "is_public": "Público para responsáveis/alunos",
        }


class HolidayForm(forms.ModelForm):
    """Formulário ModelForm para criação de feriado."""

    class Meta:
        model = Holiday
        fields = ["name", "date", "type", "is_recurring"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "type": forms.Select(attrs={"class": "form-select"}),
            "is_recurring": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "name": "Nome",
            "date": "Data",
            "type": "Tipo",
            "is_recurring": "Repete todo ano",
        }
