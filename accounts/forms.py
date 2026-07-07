"""Formulários de autenticação e conta do usuário."""

from django import forms


class LoginForm(forms.Form):
    """Formulário de autenticação por e-mail e senha."""

    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"autofocus": True, "class": "form-control"}),
    )
    password = forms.CharField(
        label="Senha", widget=forms.PasswordInput(attrs={"class": "form-control"})
    )
    remember_me = forms.BooleanField(
        required=False,
        label="Lembrar-me",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class ChangePasswordForm(forms.Form):
    """Formulário de troca de senha com confirmação."""

    current_password = forms.CharField(
        label="Senha Atual", widget=forms.PasswordInput(attrs={"class": "form-control"})
    )
    new_password = forms.CharField(
        label="Nova Senha", widget=forms.PasswordInput(attrs={"class": "form-control"})
    )
    confirm_password = forms.CharField(
        label="Confirmar Nova Senha",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    def clean(self):
        """Valida que a nova senha e a confirmação são iguais."""
        data = super().clean()
        if data.get("new_password") != data.get("confirm_password"):
            self.add_error("confirm_password", "As senhas não coincidem.")
        return data


class UserEditForm(forms.Form):
    """Formulário das informações editáveis no perfil do usuário."""

    first_name = forms.CharField(
        max_length=150,
        label="Nome",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        max_length=150,
        label="Sobrenome",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    role = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Perfil",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    is_active = forms.BooleanField(
        required=False,
        label="Ativo",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.models import Role

        self.fields["role"].queryset = Role.objects.all()
