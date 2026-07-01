"""Formulários de professores e disciplinas."""

from django import forms

from teachers.models import Subject


class SubjectForm(forms.ModelForm):
    """Formulário de cadastro de disciplina."""

    class Meta:
        model = Subject
        fields = ["name", "code", "workload"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "workload": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }
        labels = {"name": "Nome", "code": "Código", "workload": "Carga Horária (h/ano)"}


def _user_choices_queryset():
    """QuerySet preguiçoso de usuários ativos — avaliado só no render do widget."""
    from core.models import CustomUser

    return CustomUser.objects.filter(is_active=True).values_list("pk", "email")


class TeacherForm(forms.Form):
    """Formulário de criação de professor a partir de usuário existente.

    O campo `subjects` (ManyToMany) permite já atribuir disciplinas no
    momento do cadastro — caso contrário, o vínculo pode ser feito
    posteriormente pela tela de detalhe do professor.
    """

    user_id = forms.UUIDField(
        label="Usuário",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    registration_number = forms.CharField(
        max_length=30,
        label="Matrícula",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    hire_date = forms.DateField(
        required=False,
        label="Data de Admissão",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        label="Disciplinas",
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
        help_text="Segure Ctrl/Cmd para selecionar várias disciplinas.",
    )

    def __init__(self, *args, **kwargs):
        """Atribui o queryset lazy ao widget, sem forçar acesso ao banco."""
        super().__init__(*args, **kwargs)
        self.fields["user_id"].widget.choices = _user_choices_queryset()
