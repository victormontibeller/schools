"""Formulários de responsáveis e vínculos com alunos."""

from django import forms

from students.models import Student


class GuardianForm(forms.Form):
    """Formulário de criação de responsável a partir de usuário existente.

    O `user_id` preenche o `CustomUser` que passará a ter perfil de
    responsável. Os demais campos espelham o modelo `Guardian`.
    """

    user_id = forms.UUIDField(
        label="Usuário",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    relationship_type = forms.ChoiceField(
        label="Parentesco",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cpf = forms.CharField(
        max_length=14,
        required=False,
        label="CPF",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    rg = forms.CharField(
        max_length=20,
        required=False,
        label="RG",
        widget=forms.TextInput(attrs={"class": "form-control"}),
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

    def __init__(self, *args, **kwargs):
        """Popula choices de parentesco e o queryset lazy de usuários."""
        super().__init__(*args, **kwargs)
        from core.models import CustomUser
        from guardians.models import Guardian

        self.fields["relationship_type"].choices = Guardian.Relationship.choices
        self.fields["user_id"].widget.choices = CustomUser.objects.filter(
            is_active=True
        ).values_list("pk", "email")


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
