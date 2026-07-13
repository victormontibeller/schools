"""Formulários do módulo de frequência."""

from django import forms
from django.db.models import Q

from attendance.models import AttendanceJustification, AttendanceRecord


class AttendanceRecordForm(forms.ModelForm):
    """Formulário para abrir uma nova chamada."""

    class Meta:
        model = AttendanceRecord
        fields = [
            "class_obj",
            "subject",
            "teacher",
            "date",
            "lesson_number",
            "lesson_content",
            "notes",
        ]
        widgets = {
            "class_obj": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.Select(attrs={"class": "form-select"}),
            "teacher": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "lesson_number": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "lesson_content": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
        labels = {
            "class_obj": "Turma",
            "subject": "Disciplina",
            "teacher": "Professor",
            "date": "Data",
            "lesson_number": "Aula nº",
            "lesson_content": "Conteúdo Ministrado",
            "notes": "Observações (opcional)",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and getattr(getattr(user, "role", None), "name", "") == "TEACHER":
            teacher = getattr(user, "teacher_profile", None)
            if teacher:
                self.fields["teacher"].queryset = self.fields["teacher"].queryset.filter(
                    pk=teacher.pk
                )
                self.fields["teacher"].initial = teacher
                self.fields["teacher"].disabled = True
                self.fields["class_obj"].queryset = (
                    self.fields["class_obj"]
                    .queryset.filter(Q(class_teacher=teacher) | Q(schedules__teacher=teacher))
                    .distinct()
                )
                self.fields["subject"].queryset = teacher.subjects.all()


class JustificationForm(forms.ModelForm):
    """Formulário para submissão de justificativa de ausência."""

    class Meta:
        model = AttendanceJustification
        fields = ["student", "start_date", "end_date", "reason", "document"]
        widgets = {
            "student": forms.Select(attrs={"class": "form-select"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "document": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
        labels = {
            "student": "Aluno",
            "start_date": "Início",
            "end_date": "Término",
            "reason": "Motivo",
            "document": "Documento (opcional)",
        }
