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


class TeacherForm(forms.Form):
    """Formulário de criação de professor com identidade e contato próprios."""

    REQUIRED_FIELDS = (
        "first_name",
        "last_name",
        "email",
        "hire_date",
        "birth_date",
        "gender",
        "cpf",
        "rg_number",
        "phone_mobile",
    )

    first_name = forms.CharField(
        max_length=150, label="Nome", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    last_name = forms.CharField(
        max_length=150, label="Sobrenome", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    email = forms.EmailField(
        label="E-mail", widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    registration_number = forms.CharField(
        required=False,
        label="Matrícula",
        widget=forms.TextInput(
            attrs={"class": "form-control", "readonly": True, "placeholder": "Gerada ao salvar"}
        ),
    )
    avatar = forms.ImageField(
        required=False,
        label="Foto do Professor",
        widget=forms.ClearableFileInput(attrs={"class": "sm-profile-avatar-input"}),
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
    accepts_email_notifications = forms.BooleanField(
        required=False,
        label="Aceita notificações por e-mail",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    accepts_whatsapp_notifications = forms.BooleanField(
        required=False,
        label="Aceita notificações por WhatsApp",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        """Configura choices de gênero."""
        super().__init__(*args, **kwargs)
        from teachers.models import Teacher

        self.fields["gender"].choices = Teacher.Gender.choices
        for field_name in self.REQUIRED_FIELDS:
            self.fields[field_name].required = True


class TeacherEditForm(forms.Form):
    """Formulario de edicao de professor (dados do perfil, nao do usuario)."""

    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput())

    REQUIRED_FIELDS = (
        "first_name",
        "last_name",
        "hire_date",
        "birth_date",
        "gender",
        "cpf",
        "rg_number",
        "phone_mobile",
    )

    first_name = forms.CharField(
        max_length=150,
        required=False,
        label="Nome",
        widget=forms.TextInput(attrs={"class": "form-control", "data_grid": "col-12 col-md-6"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        label="Sobrenome",
        widget=forms.TextInput(attrs={"class": "form-control", "data_grid": "col-12 col-md-6"}),
    )
    email = forms.EmailField(
        label="E-mail", widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    avatar = forms.ImageField(
        required=False,
        label="Foto do Professor",
        widget=forms.ClearableFileInput(attrs={"class": "sm-profile-avatar-input"}),
    )
    registration_number = forms.CharField(
        required=False,
        max_length=30,
        label="Matrícula",
        widget=forms.TextInput(
            attrs={"class": "form-control", "readonly": True, "data_grid": "col-12 col-lg-6"}
        ),
    )
    hire_date = forms.DateField(
        required=False,
        label="Data de Admissao",
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control", "data_grid": "col-12 col-md-6"}
        ),
    )
    birth_date = forms.DateField(
        required=False,
        label="Data de Nascimento",
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control", "data_grid": "col-12 col-md-6"}
        ),
    )
    gender = forms.ChoiceField(
        required=False,
        label="Genero",
        widget=forms.Select(attrs={"class": "form-select", "data_grid": "col-12 col-md-6"}),
    )
    cpf = forms.CharField(
        max_length=14,
        required=False,
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
        required=False,
        label="RG — Numero",
        widget=forms.TextInput(attrs={"class": "form-control", "data_grid": "col-12 col-md-4"}),
    )
    phone_mobile = forms.CharField(
        max_length=20,
        required=False,
        label="Celular",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "(00) 00000-0000",
                "data_grid": "col-12 col-md-6",
            }
        ),
    )
    accepts_email_notifications = forms.BooleanField(
        required=False,
        label="Aceita notificações por e-mail",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    accepts_whatsapp_notifications = forms.BooleanField(
        required=False,
        label="Aceita notificações por WhatsApp",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from teachers.models import Teacher

        self.fields["gender"].choices = list(Teacher.Gender.choices)
        for field_name in self.REQUIRED_FIELDS:
            self.fields[field_name].required = True


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
