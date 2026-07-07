"""Formulários de responsáveis e vínculos com alunos."""

from django import forms

from students.models import Student


class GuardianForm(forms.Form):
    """Formulário de criação de responsável a partir de usuário existente."""

    user_id = forms.UUIDField(
        label="Usuário",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    relationship_type = forms.ChoiceField(
        label="Parentesco",
        widget=forms.Select(attrs={"class": "form-select"}),
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
    phone = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    phone_whatsapp = forms.CharField(
        max_length=20,
        required=False,
        label="WhatsApp",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    phone_mobile = forms.CharField(
        max_length=20,
        required=False,
        label="Celular",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "(00) 00000-0000"}),
    )

    def __init__(self, *args, **kwargs):
        """Popula choices de parentesco e o queryset lazy de usuários."""
        super().__init__(*args, **kwargs)
        from core.models import CustomUser
        from guardians.models import Guardian
        from locations.selectors import StateSelector

        self.fields["relationship_type"].choices = Guardian.Relationship.choices
        self.fields["user_id"].widget.choices = CustomUser.objects.filter(
            is_active=True
        ).values_list("pk", "email")
        self.fields["gender"].choices = [("", "---------")] + list(Guardian.Gender.choices)
        self.fields["rg_state"].choices = StateSelector().list_choices(include_blank=True)


class StudentGuardianForm(forms.Form):
    """Formulário para vincular um aluno a um responsável."""

    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        label="Aluno",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="Selecione um aluno",
    )
    is_primary = forms.BooleanField(
        required=False,
        label="Responsável Principal",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    has_custody = forms.BooleanField(
        required=False,
        initial=True,
        label="Possui Guarda Legal",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    can_pickup = forms.BooleanField(
        required=False,
        initial=True,
        label="Autorizado a Buscar",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class GuardianEditForm(forms.Form):
    """Formulario de edicao de responsavel."""

    first_name = forms.CharField(
        max_length=150,
        required=False,
        label="Nome",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        label="Sobrenome",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    avatar = forms.ImageField(
        required=False,
        label="Foto do Responsável",
        widget=forms.ClearableFileInput(attrs={"class": "sm-profile-avatar-input"}),
    )
    relationship_type = forms.ChoiceField(
        label="Parentesco",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    birth_date = forms.DateField(
        required=False,
        label="Data de Nascimento",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    gender = forms.ChoiceField(
        required=False,
        label="Genero",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    nationality = forms.CharField(
        max_length=100,
        required=False,
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
        label="RG — Numero",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    rg_issuer = forms.CharField(
        max_length=50,
        required=False,
        label="RG — Orgao Emissor",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "SSP"}),
    )
    rg_state = forms.ChoiceField(
        required=False,
        label="RG — UF",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    phone_whatsapp = forms.CharField(
        max_length=20,
        required=False,
        label="WhatsApp",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    phone_mobile = forms.CharField(
        max_length=20,
        required=False,
        label="Celular",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "(00) 00000-0000"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from guardians.models import Guardian
        from locations.selectors import StateSelector

        self.fields["relationship_type"].choices = Guardian.Relationship.choices
        self.fields["gender"].choices = [("", "---------")] + list(Guardian.Gender.choices)
        self.fields["rg_state"].choices = StateSelector().list_choices(include_blank=True)
