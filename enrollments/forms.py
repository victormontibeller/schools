"""Validação de campos dos fluxos HTTP de matrícula."""

from collections.abc import Iterable

from django import forms

from enrollments.models import DocumentRequirement, EnrollmentApplication, StudentDocument


class EnrollmentApplicationForm(forms.Form):
    """Dados de entrada da solicitação; ano letivo é derivado no service."""

    student_id = forms.ChoiceField(
        label="Aluno", widget=forms.Select(attrs={"class": "form-select"})
    )
    application_type = forms.ChoiceField(
        label="Tipo",
        choices=EnrollmentApplication.ApplicationType.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    target_class_id = forms.ChoiceField(
        label="Turma de destino",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    source_enrollment_id = forms.ChoiceField(
        label="Matrícula de origem",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    origin_school = forms.CharField(
        label="Escola de origem",
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    destination_school = forms.CharField(
        label="Escola de destino",
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    priority = forms.IntegerField(
        label="Prioridade",
        min_value=0,
        max_value=32767,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 0}),
    )
    notes = forms.CharField(
        label="Observações",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(
        self,
        *args,
        student_choices: Iterable[tuple[object, str]] = (),
        class_choices: Iterable[tuple[object, str]] = (),
        enrollment_choices: Iterable[tuple[object, str]] = (),
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["student_id"].choices = [("", "Selecione"), *student_choices]
        self.fields["target_class_id"].choices = [("", "Selecione"), *class_choices]
        self.fields["source_enrollment_id"].choices = [
            ("", "Não se aplica"),
            *enrollment_choices,
        ]


class DocumentDeliveryForm(forms.Form):
    """Entrega digital ou física de um item materializado do checklist."""

    expected_version = forms.IntegerField(widget=forms.HiddenInput())
    delivery_method = forms.ChoiceField(
        label="Forma de entrega",
        choices=StudentDocument.DeliveryMethod.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    file = forms.FileField(
        label="Arquivo",
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, allows_physical: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        choices = [(StudentDocument.DeliveryMethod.DIGITAL, "Digital")]
        if allows_physical:
            choices.append((StudentDocument.DeliveryMethod.PHYSICAL, "Físico"))
        self.fields["delivery_method"].choices = choices


class DocumentRequirementForm(forms.Form):
    """Configuração administrativa aplicada somente a solicitações futuras."""

    expected_version = forms.IntegerField(initial=0, widget=forms.HiddenInput())
    application_type = forms.ChoiceField(
        label="Tipo de solicitação",
        choices=EnrollmentApplication.ApplicationType.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    code = forms.SlugField(
        label="Código",
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    label = forms.CharField(
        label="Documento",
        max_length=120,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    is_required = forms.BooleanField(
        label="Obrigatório",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    allows_physical = forms.BooleanField(
        label="Aceita conferência física",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    display_order = forms.IntegerField(
        label="Ordem",
        min_value=0,
        max_value=32767,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 0}),
    )

    @classmethod
    def initial_for(cls, requirement: DocumentRequirement) -> dict:
        return {
            "expected_version": requirement.version,
            "application_type": requirement.application_type,
            "code": requirement.code,
            "label": requirement.label,
            "is_required": requirement.is_required,
            "allows_physical": requirement.allows_physical,
            "display_order": requirement.display_order,
        }


class EnrollmentApplicationCorrectionForm(forms.Form):
    """Campos mutáveis de uma solicitação ainda corrigível."""

    expected_version = forms.IntegerField(widget=forms.HiddenInput())
    target_class_id = forms.ChoiceField(
        label="Turma de destino",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    source_enrollment_id = forms.ChoiceField(
        label="Matrícula de origem",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    origin_school = forms.CharField(
        label="Escola de origem",
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    destination_school = forms.CharField(
        label="Escola de destino",
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    priority = forms.IntegerField(
        label="Prioridade",
        min_value=0,
        max_value=32767,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    notes = forms.CharField(
        label="Observações/justificativa",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, class_choices=(), enrollment_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_class_id"].choices = [("", "Não se aplica"), *class_choices]
        self.fields["source_enrollment_id"].choices = [
            ("", "Não se aplica"),
            *enrollment_choices,
        ]


class ReenrollmentSourceForm(forms.Form):
    """Seleciona a turma de origem da preparação da rematrícula."""

    source_class_id = forms.ChoiceField(
        label="Turma de origem", widget=forms.Select(attrs={"class": "form-select"})
    )

    def __init__(self, *args, class_choices=(), **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["source_class_id"].choices = [("", "Selecione"), *class_choices]
