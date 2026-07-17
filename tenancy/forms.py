"""Formulários do catálogo público de escolas."""

from django import forms


class PlatformSchoolCreateForm(forms.Form):
    """Cadastro de uma escola e de seu domínio primário."""

    name = forms.CharField(
        max_length=200,
        label="Nome da escola",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    schema_name = forms.RegexField(
        regex=r"^[a-z][a-z0-9_]{2,62}$",
        max_length=63,
        label="Schema",
        help_text="Use letras minúsculas, números e sublinhado; comece com uma letra.",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "escola_modelo"}),
    )
    domain = forms.CharField(
        max_length=253,
        label="Domínio principal",
        help_text="Informe somente o host, sem http:// ou caminho.",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "escola.localhost"}),
    )
    email = forms.EmailField(
        required=False,
        label="E-mail institucional",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        required=False,
        max_length=20,
        label="Telefone",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def clean_domain(self) -> str:
        """Normaliza e valida o host informado."""
        from tenancy.domain_validation import normalize_domain

        return normalize_domain(self.cleaned_data["domain"])


class PlatformSchoolEditForm(forms.Form):
    """Edição dos dados públicos de uma escola provisionada."""

    name = forms.CharField(
        max_length=200,
        label="Nome da escola",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    domain = forms.CharField(
        max_length=253,
        label="Domínio principal",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        required=False,
        label="E-mail institucional",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        required=False,
        max_length=20,
        label="Telefone",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    resend_domain = forms.CharField(
        required=False,
        max_length=253,
        label="Domínio de envio na Resend",
        help_text="Verifique SPF e DKIM manualmente no painel da Resend.",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "mail.escola.com"}),
    )
    resend_from_email = forms.EmailField(
        required=False,
        label="Remetente de e-mail",
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "agenda@mail.escola.com"}
        ),
    )
    resend_verified = forms.BooleanField(
        required=False,
        label="Domínio confirmado como verificado na Resend",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    is_active = forms.BooleanField(
        required=False,
        label="Escola ativa",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_domain(self) -> str:
        """Normaliza e valida o host informado."""
        from tenancy.domain_validation import normalize_domain

        return normalize_domain(self.cleaned_data["domain"])
