"""Fachada estável dos formulários HTTP do domínio financeiro."""

import uuid

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError

from financeiro.models import PaymentRecord, StudentFinancialContract


class StudentFinancialContractForm(forms.ModelForm):
    """Criação e edição do snapshot de um contrato financeiro."""

    class Meta:
        model = StudentFinancialContract
        fields = [
            "template",
            "student",
            "class_obj",
            "academic_year",
            "name",
            "billing_frequency",
            "installment_count",
            "installment_value",
            "due_day",
            "start_competency",
            "discount_value",
            "late_fee_percent",
            "daily_interest_percent",
            "notes",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-select"}),
            "template": forms.Select(attrs={"class": "form-select"}),
            "class_obj": forms.Select(attrs={"class": "form-select"}),
            "academic_year": forms.NumberInput(
                attrs={"class": "form-control", "min": 2000, "max": 2100}
            ),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "billing_frequency": forms.Select(attrs={"class": "form-select"}),
            "installment_count": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 60}
            ),
            "installment_value": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
            ),
            "due_day": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 28}),
            "start_competency": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "discount_value": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "late_fee_percent": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "max": "100"}
            ),
            "daily_interest_percent": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.0001", "min": "0"}
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
        labels = {
            "student": "Aluno",
            "template": "Modelo de plano",
            "class_obj": "Turma",
            "academic_year": "Ano letivo",
            "name": "Nome do contrato",
            "billing_frequency": "Frequência de cobrança",
            "installment_count": "Número de parcelas",
            "installment_value": "Valor da parcela",
            "due_day": "Dia de vencimento",
            "start_competency": "Competência inicial",
            "discount_value": "Desconto por parcela",
            "late_fee_percent": "Multa por atraso (%)",
            "daily_interest_percent": "Juros diários (%)",
            "notes": "Observações",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in (
            "class_obj",
            "template",
            "start_competency",
            "discount_value",
            "late_fee_percent",
            "daily_interest_percent",
            "notes",
        ):
            self.fields[name].required = False


class MaterializeBillingsByClassForm(forms.Form):
    """Geração idempotente por turma e competência."""

    class_obj = forms.ChoiceField(
        label="Turma", widget=forms.Select(attrs={"class": "form-select"})
    )
    academic_year = forms.IntegerField(
        label="Ano letivo",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 2000, "max": 2100}),
    )
    month = forms.ChoiceField(
        label="Competência (mês)",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from classes.selectors import ClassSelector

        classes = ClassSelector().list_ordered()
        self.fields["class_obj"].choices = [("", "---")] + [
            (str(item.pk), str(item)) for item in classes
        ]
        self.fields["month"].choices = [("", "Mês corrente")] + [
            (str(month), f"{month:02d}") for month in range(1, 13)
        ]


class PaymentForm(forms.ModelForm):
    """Baixa manual para uma única cobrança."""

    class Meta:
        model = PaymentRecord
        fields = ["amount", "paid_date", "payment_method", "reference", "notes"]
        widgets = {
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
            ),
            "paid_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "payment_method": forms.Select(attrs={"class": "form-select"}),
            "reference": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notes"].required = False
        self.fields["reference"].required = False
        self.fields["idempotency_key"] = forms.UUIDField(
            initial=uuid.uuid4, widget=forms.HiddenInput()
        )


class RenegotiationForm(forms.Form):
    new_due_date = forms.DateField(
        label="Novo vencimento (1ª parcela)",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    new_value = forms.DecimalField(
        label="Valor renegociado (total)",
        required=False,
        min_value=0,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
    )
    installment_count = forms.IntegerField(
        label="Número de parcelas",
        min_value=1,
        max_value=12,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 12}),
    )

    def clean_new_value(self):
        value = self.cleaned_data.get("new_value")
        if value is not None and value <= 0:
            raise DjangoValidationError("Valor renegociado deve ser maior que zero.")
        return value


class CancelBillingForm(forms.Form):
    reason = forms.CharField(
        label="Motivo do cancelamento",
        required=True,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class ReportFilterForm(forms.Form):
    year = forms.IntegerField(
        label="Ano",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 2000, "max": 2100}),
    )
    month = forms.ChoiceField(
        label="Mês", required=False, widget=forms.Select(attrs={"class": "form-select"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["month"].choices = [("", "Ano inteiro")] + [
            (str(month), f"{month:02d}") for month in range(1, 13)
        ]


from financeiro.receivables_forms import (  # noqa: E402,F401
    AdHocBillingForm,
    CollectionReminderPolicyForm,
    FinancialContractAmendmentForm,
    FinancialPlanTemplateForm,
    PaymentBatchForm,
    PaymentReversalForm,
)

__all__ = [
    "AdHocBillingForm",
    "CancelBillingForm",
    "CollectionReminderPolicyForm",
    "FinancialContractAmendmentForm",
    "FinancialPlanTemplateForm",
    "MaterializeBillingsByClassForm",
    "PaymentBatchForm",
    "PaymentForm",
    "PaymentReversalForm",
    "RenegotiationForm",
    "ReportFilterForm",
    "StudentFinancialContractForm",
]
