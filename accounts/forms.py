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
