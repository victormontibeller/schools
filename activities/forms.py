"""Formulários de atividades."""

from decimal import Decimal

from django import forms

from activities.models import Activity
from classes.models import Class
from students.models import Student
from teachers.models import Subject, Teacher


class ActivityForm(forms.Form):
    """Formulário para criação de atividade com seleção por dropdown."""

    class_obj = forms.ModelChoiceField(label="Turma", queryset=Class.objects.all())
    subject = forms.ModelChoiceField(label="Disciplina", queryset=Subject.objects.all())
    teacher = forms.ModelChoiceField(label="Professor", queryset=Teacher.objects.all())
    title = forms.CharField(label="Título", max_length=200)
    description = forms.CharField(
        label="Descrição", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    type = forms.ChoiceField(
        label="Tipo", choices=Activity.Type.choices, initial=Activity.Type.HOMEWORK
    )
    due_date = forms.DateField(
        label="Data de Entrega", widget=forms.DateInput(attrs={"type": "date"})
    )
    max_score = forms.DecimalField(
        label="Nota Máxima", initial=Decimal("10.00"), max_digits=5, decimal_places=2
    )
    weight = forms.DecimalField(
        label="Peso na Média", initial=Decimal("1.00"), max_digits=4, decimal_places=2
    )


class ScoreForm(forms.Form):
    """Formulário para lançar a nota de um aluno numa atividade."""

    student = forms.ModelChoiceField(label="Aluno", queryset=Student.objects.all())
    score = forms.DecimalField(label="Nota", max_digits=5, decimal_places=2)
    feedback = forms.CharField(
        label="Feedback", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
