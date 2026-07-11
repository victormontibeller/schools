"""Formulários de autenticação e conta do usuário."""

from django import forms


class DemoSignupForm(forms.Form):
    """Cadastro temporário e verificado no tenant de demonstração."""

    first_name = forms.CharField(
        max_length=150,
        label="Nome",
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        max_length=150,
        label="Sobrenome",
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "family-name"}),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )
    confirm_password = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )

    def clean(self):
        """Confirma que as duas senhas são iguais."""
        data = super().clean()
        if data.get("password") != data.get("confirm_password"):
            self.add_error("confirm_password", "As senhas não coincidem.")
        return data


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
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
    )
    avatar = forms.ImageField(
        required=False,
        label="Foto do Usuário",
        widget=forms.ClearableFileInput(attrs={"class": "sm-profile-avatar-input"}),
    )
    last_name = forms.CharField(
        max_length=150,
        label="Sobrenome",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        max_length=20,
        label="Telefone",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    role = forms.ModelChoiceField(
        queryset=None,
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


class PlatformUserCreateForm(forms.Form):
    """Cadastro de operador do painel público."""

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
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    password = forms.CharField(
        label="Senha inicial",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    confirm_password = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    is_superuser = forms.BooleanField(
        required=False,
        label="Superusuário da plataforma",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean(self):
        """Confirma a senha inicial."""
        data = super().clean()
        if data.get("password") != data.get("confirm_password"):
            self.add_error("confirm_password", "As senhas não coincidem.")
        return data


class PlatformUserEditForm(forms.Form):
    """Edição de operador do painel público."""

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
    is_active = forms.BooleanField(
        required=False,
        label="Usuário ativo",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    is_superuser = forms.BooleanField(
        required=False,
        label="Superusuário da plataforma",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
