"""Formularios do modulo core (escola)."""

from django import forms


class BusinessUnitForm(forms.Form):
    """Formulario de criacao e edicao de unidades de negocio."""

    name = forms.CharField(
        max_length=200,
        label="Nome da Empresa",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    legal_name = forms.CharField(
        max_length=255,
        required=False,
        label="Razao Social",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    trade_name = forms.CharField(
        max_length=255,
        required=False,
        label="Nome Fantasia",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    cnpj = forms.CharField(
        max_length=18,
        required=False,
        label="CNPJ",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "00.000.000/0000-00"}
        ),
    )
    state_registration = forms.CharField(
        max_length=20,
        required=False,
        label="Inscricao Estadual",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    municipal_registration = forms.CharField(
        max_length=20,
        required=False,
        label="Inscricao Municipal",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        required=False,
        label="E-mail",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    logo = forms.ImageField(
        required=False,
        label="Logotipo",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )
    academic_year_start = forms.DateField(
        required=False,
        label="Inicio do Ano Letivo",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    academic_year_end = forms.DateField(
        required=False,
        label="Fim do Ano Letivo",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    contact_full_name = forms.CharField(
        max_length=255,
        required=False,
        label="Nome do Responsavel",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contact_role = forms.CharField(
        max_length=150,
        required=False,
        label="Cargo do Responsavel",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contact_phone = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone do Responsavel",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contact_email = forms.EmailField(
        required=False,
        label="E-mail do Responsavel",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )


class SchoolEditForm(forms.Form):
    """Formulario de edicao dos dados institucionais, contato e logo da escola."""

    name = forms.CharField(
        max_length=200,
        label="Nome da Escola",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    legal_name = forms.CharField(
        max_length=255,
        required=False,
        label="Razao Social",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    trade_name = forms.CharField(
        max_length=255,
        required=False,
        label="Nome Fantasia",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    cnpj = forms.CharField(
        max_length=18,
        required=False,
        label="CNPJ",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "00.000.000/0000-00"}
        ),
    )
    state_registration = forms.CharField(
        max_length=20,
        required=False,
        label="Inscricao Estadual",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    municipal_registration = forms.CharField(
        max_length=20,
        required=False,
        label="Inscricao Municipal",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        required=False,
        label="E-mail",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    logo = forms.ImageField(
        required=False,
        label="Logotipo",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )
    academic_year_start = forms.DateField(
        required=False,
        label="Inicio do Ano Letivo",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    academic_year_end = forms.DateField(
        required=False,
        label="Fim do Ano Letivo",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    contact_full_name = forms.CharField(
        max_length=255,
        required=False,
        label="Nome do Responsavel",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contact_role = forms.CharField(
        max_length=150,
        required=False,
        label="Cargo do Responsavel",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contact_phone = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone do Responsavel",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contact_email = forms.EmailField(
        required=False,
        label="E-mail do Responsavel",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
