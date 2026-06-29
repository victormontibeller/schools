"""Formulários do módulo de frequência."""

from django import forms

from attendance.models import AttendanceJustification, AttendanceRecord


class AttendanceRecordForm(forms.ModelForm):
    """Formulário para abrir uma nova chamada."""

    class Meta:
        model = AttendanceRecord
        fields = ["class_obj", "subject", "teacher", "date", "lesson_number", "notes"]
        labels = {
            "class_obj": "Turma",
            "subject": "Disciplina",
            "teacher": "Professor",
            "date": "Data",
            "lesson_number": "Aula nº",
            "notes": "Observações",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class JustificationForm(forms.ModelForm):
    """Formulário para submissão de justificativa de ausência."""

    class Meta:
        model = AttendanceJustification
        fields = ["student", "start_date", "end_date", "reason", "document"]
        labels = {
            "student": "Aluno",
            "start_date": "Início",
            "end_date": "Término",
            "reason": "Motivo",
            "document": "Documento (opcional)",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 2}),
        }
