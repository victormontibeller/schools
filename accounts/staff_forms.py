"""Formulários de convite da equipe escolar."""

from django import forms


class StaffUserForm(forms.Form):
    """Coleta somente identidade e papel, nunca uma senha compartilhada."""

    first_name = forms.CharField(
        label="Nome", max_length=150, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    last_name = forms.CharField(
        label="Sobrenome", max_length=150, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    email = forms.EmailField(
        label="E-mail", widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    role_name = forms.ChoiceField(
        label="Papel",
        choices=[
            ("SECRETARY", "Secretaria"),
            ("COORDINATOR", "Coordenação"),
            ("FINANCE", "Financeiro"),
            ("ADMIN", "Administrador"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class BootstrapAdministratorForm(forms.Form):
    """Identidade do primeiro administrador, após configurar o remetente."""

    first_name = forms.CharField(
        label="Nome", max_length=150, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    last_name = forms.CharField(
        label="Sobrenome", max_length=150, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    email = forms.EmailField(
        label="E-mail do administrador", widget=forms.EmailInput(attrs={"class": "form-control"})
    )
