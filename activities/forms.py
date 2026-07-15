"""Formulários de atividades."""

from decimal import Decimal

from django import forms

from activities.models import Activity
from classes.contracts import Class
from students.contracts import Student
from teachers.contracts import Subject, Teacher


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
    modality = forms.ChoiceField(
        label="Modalidade",
        choices=Activity.Modality.choices,
        initial=Activity.Modality.INDIVIDUAL,
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and getattr(getattr(user, "role", None), "name", "") == "TEACHER":
            teacher = getattr(user, "teacher_profile", None)
            if teacher:
                self.fields["teacher"].queryset = Teacher.objects.filter(pk=teacher.pk)
                self.fields["teacher"].initial = teacher
                self.fields["teacher"].disabled = True
                self.fields["class_obj"].queryset = Class.objects.filter(
                    schedules__teacher=teacher
                ).distinct()
                self.fields["subject"].queryset = teacher.subjects.filter(
                    schedules__teacher=teacher
                ).distinct()


class ActivityEditForm(ActivityForm):
    """Formulário dos campos editáveis no card de informações da atividade."""

    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput())


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
        required=False,
        label="Feedback",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class ActivityGroupForm(forms.Form):
    """Formulário de composição de um grupo da atividade."""

    name = forms.CharField(
        label="Nome do grupo",
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    students = forms.ModelMultipleChoiceField(
        label="Integrantes",
        queryset=Student.objects.none(),
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 6}),
    )

    def __init__(self, *args, activity=None, **kwargs):
        super().__init__(*args, **kwargs)
        if activity:
            self.fields["students"].queryset = Student.objects.filter(
                enrollments__class_obj=activity.class_obj,
                enrollments__status="ACTIVE",
            ).distinct()


class ActivityGroupResultForm(forms.Form):
    """Formulário do resultado coletivo aplicado aos integrantes."""

    score = forms.DecimalField(
        label="Nota do grupo",
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
    )
    feedback = forms.CharField(
        label="Feedback do grupo",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
