"""Formulários HTTP sem consultas nem regras de atendimento."""

from django import forms


class StyledForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                (
                    "form-check-input"
                    if isinstance(field.widget, forms.CheckboxInput)
                    else "form-select" if isinstance(field.widget, forms.Select) else "form-control"
                ),
            )


class ResponseForm(StyledForm):
    version = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    body = forms.CharField(
        label="Mensagem", max_length=20000, widget=forms.Textarea(attrs={"rows": 3})
    )
    file = forms.FileField(label="Anexo PDF ou imagem (opcional)", required=False)


class RequestForm(ResponseForm):
    subject = forms.CharField(label="Assunto", max_length=180)
    student_id = forms.ChoiceField(label="Criança")
    department_id = forms.ChoiceField(label="Setor")
    field_order = ["student_id", "department_id", "subject", "body", "file", "version"]

    def __init__(self, *args, student_choices, department_choices, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student_id"].choices = student_choices
        self.fields["department_id"].choices = department_choices


class CalendarForm(StyledForm):
    version = forms.IntegerField(widget=forms.HiddenInput(), initial=0)
    weekdays = forms.TypedMultipleChoiceField(
        label="Dias de atendimento",
        coerce=int,
        choices=enumerate(["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]),
    )
    opens_at = forms.TimeField(label="Abertura", widget=forms.TimeInput(attrs={"type": "time"}))
    closes_at = forms.TimeField(
        label="Encerramento", widget=forms.TimeInput(attrs={"type": "time"})
    )
    closed_dates = forms.CharField(
        label="Feriados e fechamentos (uma data AAAA-MM-DD por linha)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    immediate_contact = forms.CharField(label="Contato imediato da escola", max_length=200)

    def clean_closed_dates(self):
        return self.cleaned_data["closed_dates"].split()


class DepartmentForm(StyledForm):
    code = forms.CharField(widget=forms.HiddenInput())
    version = forms.IntegerField(widget=forms.HiddenInput(), initial=0)
    enabled = forms.BooleanField(label="Habilitar atendimento do setor", required=False)
    user_ids = forms.MultipleChoiceField(
        label="Atendentes ativos com capacidade no setor", required=False
    )

    def __init__(self, *args, user_choices, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user_ids"].choices = user_choices
