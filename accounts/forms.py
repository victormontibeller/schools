from django import forms


class LoginForm(forms.Form):
    """Formulário de autenticação por e-mail e senha."""

    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autofocus": True}))
    password = forms.CharField(label="Senha", widget=forms.PasswordInput)
    remember_me = forms.BooleanField(required=False, label="Lembrar-me")


class ChangePasswordForm(forms.Form):
    """Formulário de troca de senha com confirmação."""

    current_password = forms.CharField(label="Senha Atual", widget=forms.PasswordInput)
    new_password = forms.CharField(label="Nova Senha", widget=forms.PasswordInput)
    confirm_password = forms.CharField(label="Confirmar Nova Senha", widget=forms.PasswordInput)

    def clean(self):
        """Valida que a nova senha e a confirmação são iguais."""
        data = super().clean()
        if data.get("new_password") != data.get("confirm_password"):
            self.add_error("confirm_password", "As senhas não coincidem.")
        return data
