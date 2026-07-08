"""Formularios de matriculas e secretaria."""

from django import forms

from enrollments.models import EnrollmentApplication, StudentDocument


class EnrollmentApplicationForm(forms.ModelForm):
    """Formulario de criacao de solicitacao de matricula."""

    class Meta:
        model = EnrollmentApplication
        fields = [
            "student",
            "class_obj",
            "academic_year",
            "application_type",
            "priority",
            "notes",
            "previous_class",
            "previous_school",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-select"}),
            "class_obj": forms.Select(attrs={"class": "form-select"}),
            "academic_year": forms.NumberInput(
                attrs={"class": "form-control", "min": 2000, "max": 2100}
            ),
            "application_type": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "previous_class": forms.Select(attrs={"class": "form-select"}),
            "previous_school": forms.TextInput(attrs={"class": "form-control"}),
        }
        labels = {
            "student": "Aluno",
            "class_obj": "Turma",
            "academic_year": "Ano Letivo",
            "application_type": "Tipo de Solicitacao",
            "priority": "Prioridade",
            "notes": "Observacoes",
            "previous_class": "Turma de Origem",
            "previous_school": "Escola de Origem",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["previous_class"].required = False
        self.fields["previous_school"].required = False


class StudentDocumentForm(forms.ModelForm):
    """Formulario de documento do aluno."""

    class Meta:
        model = StudentDocument
        fields = ["student", "application", "document_type", "description", "file"]
        widgets = {
            "student": forms.Select(attrs={"class": "form-select"}),
            "application": forms.Select(attrs={"class": "form-select"}),
            "document_type": forms.Select(attrs={"class": "form-select"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
        labels = {
            "student": "Aluno",
            "application": "Solicitacao",
            "document_type": "Tipo de Documento",
            "description": "Descricao",
            "file": "Arquivo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["application"].required = False
        self.fields["file"].required = False


class BulkReenrollForm(forms.Form):
    """Formulario de rematricula em lote."""

    from_class = forms.ChoiceField(
        label="Turma de Origem",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    to_academic_year = forms.IntegerField(
        label="Novo Ano Letivo",
        min_value=2000,
        max_value=2100,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from classes.selectors import ClassSelector

        classes = ClassSelector().list_ordered()
        self.fields["from_class"].choices = [
            ("", "---"),
            *[(str(c.pk), str(c)) for c in classes],
        ]
