"""Formulários de responsáveis e vínculos com alunos."""

from django import forms

from students.contracts import Student


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


class GuardianLinkForm(forms.Form):
    """Campos do vínculo editados no contexto de um aluno."""

    relationship_type = forms.ChoiceField(
        label="Parentesco", widget=forms.Select(attrs={"class": "form-select"})
    )
    is_primary = forms.BooleanField(
        required=False,
        label="Responsável principal",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    has_custody = forms.BooleanField(
        required=False,
        initial=True,
        label="Possui guarda legal",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    can_pickup = forms.BooleanField(
        required=False,
        initial=True,
        label="Autorizado a buscar",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from guardians.models import Guardian

        self.fields["relationship_type"].choices = Guardian.Relationship.choices
        for field in self.fields.values():
            field.widget.attrs["data_grid"] = "col-12 col-sm-4"


class GuardianCreateForm(GuardianLinkForm):
    """Cadastro de contato e vínculo inicial, sem criar conta de acesso."""

    first_name = forms.CharField(
        max_length=150, label="Nome", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    last_name = forms.CharField(
        max_length=150, label="Sobrenome", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    email = forms.EmailField(
        label="E-mail", widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    avatar = forms.ImageField(
        required=False,
        label="Foto",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )
    accepts_email_notifications = forms.BooleanField(
        required=False,
        label="Aceita notificações por e-mail",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    accepts_whatsapp_notifications = forms.BooleanField(
        required=False,
        label="Aceita notificações por WhatsApp",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O parentesco pertence ao vínculo; os dados pessoais pertencem ao contato.
        for name in (
            "birth_date",
            "gender",
            "cpf",
            "rg_number",
            "phone_mobile",
        ):
            if name not in self.fields:
                self.fields[name] = GuardianEditForm.base_fields[name]
        from guardians.models import Guardian

        self.fields["gender"].choices = Guardian.Gender.choices
        for field_name, field in self.fields.items():
            if field_name not in {
                "avatar",
                "is_primary",
                "has_custody",
                "can_pickup",
                "accepts_email_notifications",
                "accepts_whatsapp_notifications",
            }:
                field.required = True
        self.fields["avatar"].widget.attrs["class"] = "sm-profile-avatar-input"
        for field_name, field in self.fields.items():
            if field_name != "avatar":
                field.widget.attrs["data_grid"] = "col-12 col-sm-4"
        self.order_fields(
            [
                "first_name",
                "last_name",
                "email",
                "avatar",
                "birth_date",
                "gender",
                "cpf",
                "rg_number",
                "phone_mobile",
                "accepts_email_notifications",
                "accepts_whatsapp_notifications",
                "relationship_type",
                "is_primary",
                "has_custody",
                "can_pickup",
            ]
        )


class GuardianEditForm(forms.Form):
    """Formulario de edicao de responsavel."""

    version = forms.IntegerField(required=False, min_value=0, widget=forms.HiddenInput())

    REQUIRED_FIELDS = (
        "first_name",
        "last_name",
        "email",
        "birth_date",
        "gender",
        "cpf",
        "rg_number",
        "phone_mobile",
    )

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
    email = forms.EmailField(
        required=False, label="E-mail", widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    avatar = forms.ImageField(
        required=False,
        label="Foto do Responsável",
        widget=forms.ClearableFileInput(attrs={"class": "sm-profile-avatar-input"}),
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
    phone_mobile = forms.CharField(
        max_length=20,
        required=False,
        label="Celular",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "(00) 00000-0000"}),
    )
    accepts_email_notifications = forms.BooleanField(
        required=False,
        label="Aceita notificações por e-mail",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    accepts_whatsapp_notifications = forms.BooleanField(
        required=False,
        label="Aceita notificações por WhatsApp",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, require_version=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["version"].required = require_version
        from guardians.models import Guardian

        self.fields["gender"].choices = Guardian.Gender.choices
        for field_name in self.REQUIRED_FIELDS:
            self.fields[field_name].required = True
        self.order_fields(
            [
                "first_name",
                "last_name",
                "email",
                "avatar",
                "birth_date",
                "gender",
                "cpf",
                "rg_number",
                "phone_mobile",
                "accepts_email_notifications",
                "accepts_whatsapp_notifications",
                "version",
            ]
        )


class GuardianContactEditForm(GuardianEditForm):
    """Edição da pessoa dentro do perfil do aluno, sem campos do vínculo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, require_version=True, **kwargs)
        self.fields.pop("relationship_type", None)
        for field_name, field in self.fields.items():
            if field_name != "avatar":
                field.widget.attrs["data_grid"] = "col-12 col-sm-4"
