"""Formulários de acesso temporário da plataforma."""

from django import forms


class SupportAccessForm(forms.Form):
    """Solicita tenant e motivo para uma concessão temporária."""

    tenant_id = forms.ChoiceField(
        label="Escola",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    reason = forms.CharField(
        label="Motivo do acesso",
        min_length=10,
        max_length=500,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from tenancy.models import School

        self.fields["tenant_id"].choices = [
            (str(item.pk), item.name)
            for item in School.objects.filter(is_active=True).order_by("name")
            if item.schema_name != "public"
        ]


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
        domain = self.cleaned_data["domain"].strip().lower()
        if "://" in domain or "/" in domain or " " in domain:
            raise forms.ValidationError("Informe apenas o domínio, sem protocolo ou caminho.")
        return domain


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
    is_active = forms.BooleanField(
        required=False,
        label="Escola ativa",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_domain(self) -> str:
        """Normaliza e valida o host informado."""
        domain = self.cleaned_data["domain"].strip().lower()
        if "://" in domain or "/" in domain or " " in domain:
            raise forms.ValidationError("Informe apenas o domínio, sem protocolo ou caminho.")
        return domain
