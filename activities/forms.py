"""Formulários de atividades."""

from decimal import Decimal

from django import forms

from activities.models import Activity
from classes.models import Class
from students.models import Student
from teachers.models import Subject, Teacher


class ActivityForm(forms.Form):
    """Formulário para criação de atividade com seleção por dropdown."""

    class_obj = forms.ModelChoiceField(
        label="Turma",
        queryset=Class.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    subject = forms.ModelChoiceField(
        label="Disciplina",
        queryset=Subject.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    teacher = forms.ModelChoiceField(
        label="Professor",
        queryset=Teacher.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    title = forms.CharField(
        label="Título",
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    description = forms.CharField(
        label="Descrição",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    type = forms.ChoiceField(
        label="Tipo",
        choices=Activity.Type.choices,
        initial=Activity.Type.HOMEWORK,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    due_date = forms.DateField(
        label="Data de Entrega",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    max_score = forms.DecimalField(
        label="Nota Máxima",
        initial=Decimal("10.00"),
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    weight = forms.DecimalField(
        label="Peso na Média",
        initial=Decimal("1.00"),
        max_digits=4,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )


class ActivityEditForm(ActivityForm):
    """Formulário dos campos editáveis no card de informações da atividade."""

    class_obj = None
    subject = None
    teacher = None


class ScoreForm(forms.Form):
    """Formulário para lançar a nota de um aluno numa atividade."""

    student = forms.ModelChoiceField(
        label="Aluno",
        queryset=Student.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    score = forms.DecimalField(
        label="Nota",
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    feedback = forms.CharField(
        label="Feedback",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
