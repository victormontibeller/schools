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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True


def _user_choices_queryset():
    """QuerySet preguiçoso de usuários ativos — avaliado só no render do widget."""
    from core.models import CustomUser

    return CustomUser.objects.filter(is_active=True).values_list("pk", "email")


class TeacherForm(forms.Form):
    """Formulário de criação de professor a partir de usuário existente."""

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
    birth_date = forms.DateField(
        required=False,
        label="Data de Nascimento",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    gender = forms.ChoiceField(
        required=False,
        label="Gênero",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    nationality = forms.CharField(
        max_length=100,
        required=False,
        initial="Brasileiro(a)",
        label="Nacionalidade",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    cpf = forms.CharField(
        max_length=14,
        required=False,
        label="CPF",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "000.000.000-00"}),
    )
    rg_number = forms.CharField(
        max_length=20,
        required=False,
        label="RG — Número",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    rg_issuer = forms.CharField(
        max_length=50,
        required=False,
        label="RG — Órgão Emissor",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "SSP"}),
    )
    rg_state = forms.ChoiceField(
        required=False,
        label="RG — UF",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    phone_mobile = forms.CharField(
        max_length=20,
        required=False,
        label="Celular",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "(00) 00000-0000"}),
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        label="Disciplinas",
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
        help_text="Segure Ctrl/Cmd para selecionar várias disciplinas.",
    )

    def __init__(self, *args, **kwargs):
        """Atribui choices lazy para Select widgets."""
        super().__init__(*args, **kwargs)
        self.fields["user_id"].widget.choices = _user_choices_queryset()
        from locations.selectors import StateSelector
        from teachers.models import Teacher

        self.fields["gender"].choices = [("", "---------")] + list(Teacher.Gender.choices)
        self.fields["rg_state"].choices = StateSelector().list_choices(include_blank=True)


class TeacherEditForm(forms.Form):
    """Formulario de edicao de professor (dados do perfil, nao do usuario)."""

    first_name = forms.CharField(
        max_length=150,
        label="Nome",
        widget=forms.TextInput(attrs={"class": "form-control", "data_grid": "col-12 col-md-6"}),
    )
    last_name = forms.CharField(
        max_length=150,
        label="Sobrenome",
        widget=forms.TextInput(attrs={"class": "form-control", "data_grid": "col-12 col-md-6"}),
    )
    avatar = forms.ImageField(
        required=False,
        label="Foto do Professor",
        widget=forms.ClearableFileInput(attrs={"class": "sm-profile-avatar-input"}),
    )
    registration_number = forms.CharField(
        max_length=30,
        label="Matricula",
        widget=forms.TextInput(attrs={"class": "form-control", "data_grid": "col-12 col-lg-6"}),
    )
    hire_date = forms.DateField(
        label="Data de Admissao",
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control", "data_grid": "col-12 col-md-6"}
        ),
    )
    birth_date = forms.DateField(
        label="Data de Nascimento",
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control", "data_grid": "col-12 col-md-6"}
        ),
    )
    gender = forms.ChoiceField(
        label="Genero",
        widget=forms.Select(attrs={"class": "form-select", "data_grid": "col-12 col-md-6"}),
    )
    nationality = forms.CharField(
        max_length=100,
        label="Nacionalidade",
        widget=forms.TextInput(attrs={"class": "form-control", "data_grid": "col-12 col-md-6"}),
    )
    cpf = forms.CharField(
        max_length=14,
        label="CPF",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "000.000.000-00",
                "data_grid": "col-12 col-md-6",
            }
        ),
    )
    rg_number = forms.CharField(
        max_length=20,
        label="RG — Numero",
        widget=forms.TextInput(attrs={"class": "form-control", "data_grid": "col-12 col-md-4"}),
    )
    rg_issuer = forms.CharField(
        max_length=50,
        label="RG — Orgao Emissor",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "SSP", "data_grid": "col-12 col-md-4"}
        ),
    )
    rg_state = forms.ChoiceField(
        label="RG — UF",
        widget=forms.Select(attrs={"class": "form-select", "data_grid": "col-12 col-md-4"}),
    )
    phone_mobile = forms.CharField(
        max_length=20,
        label="Celular",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "(00) 00000-0000",
                "data_grid": "col-12 col-md-6",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from locations.selectors import StateSelector
        from teachers.models import Teacher

        self.fields["gender"].choices = list(Teacher.Gender.choices)
        self.fields["rg_state"].choices = StateSelector().list_choices()


class TeacherSubjectsForm(forms.Form):
    """Formulário de vínculo entre professor e disciplinas."""

    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.none(),
        required=False,
        label="Disciplinas ministradas",
        widget=forms.SelectMultiple(attrs={"class": "form-select sm-subjects-select", "size": "6"}),
        help_text="Selecione todas as disciplinas ministradas pelo professor.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from teachers.models import Subject

        self.fields["subjects"].queryset = Subject.objects.all()
