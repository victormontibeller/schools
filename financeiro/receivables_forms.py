"""Formulários dos fluxos operacionais de contas a receber 2.0."""

import uuid

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError

from financeiro.models import (
    BillingEntry,
    CollectionReminderPolicy,
    FinancialContractAmendment,
    FinancialPlanTemplate,
    PaymentRecord,
)


class FinancialPlanTemplateForm(forms.ModelForm):
    """Cadastro dos termos reutilizáveis para contratos futuros."""

    class Meta:
        model = FinancialPlanTemplate
        fields = [
            "name",
            "academic_year",
            "billing_frequency",
            "installment_count",
            "installment_value",
            "due_day",
            "discount_value",
            "late_fee_percent",
            "daily_interest_percent",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "academic_year": forms.NumberInput(attrs={"class": "form-control"}),
            "billing_frequency": forms.Select(attrs={"class": "form-select"}),
            "installment_count": forms.NumberInput(attrs={"class": "form-control"}),
            "installment_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "due_day": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 28}),
            "discount_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "late_fee_percent": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "daily_interest_percent": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.0001"}
            ),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class FinancialContractAmendmentForm(forms.ModelForm):
    """Aditivo futuro de contrato ativo."""

    installment_count = forms.IntegerField(
        label="Quantidade de parcelas", required=False, min_value=1, max_value=60
    )
    installment_value = forms.DecimalField(
        label="Valor por parcela", required=False, min_value=0.01, decimal_places=2
    )
    due_day = forms.IntegerField(
        label="Dia de vencimento", required=False, min_value=1, max_value=28
    )
    discount_value = forms.DecimalField(
        label="Desconto", required=False, min_value=0, decimal_places=2
    )
    late_fee_percent = forms.DecimalField(
        label="Multa (%)", required=False, min_value=0, decimal_places=2
    )
    daily_interest_percent = forms.DecimalField(
        label="Juros diários (%)", required=False, min_value=0, decimal_places=4
    )

    class Meta:
        model = FinancialContractAmendment
        fields = ["effective_competency", "reason"]
        widgets = {
            "effective_competency": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    @property
    def changed_terms(self):
        return {
            name: self.cleaned_data[name]
            for name in (
                "installment_count",
                "installment_value",
                "due_day",
                "discount_value",
                "late_fee_percent",
                "daily_interest_percent",
            )
            if self.cleaned_data.get(name) is not None
        }


class AdHocBillingForm(forms.ModelForm):
    """Cobrança avulsa sem contrato obrigatório."""

    class Meta:
        model = BillingEntry
        fields = [
            "student",
            "category",
            "description",
            "principal_value",
            "discount_value",
            "competency",
            "due_date",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "principal_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "discount_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "competency": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }


class PaymentBatchForm(forms.Form):
    """Baixa única distribuída entre cobranças abertas de um aluno."""

    paid_date = forms.DateField(
        label="Data do pagamento",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    payment_method = forms.ChoiceField(
        label="Forma de pagamento",
        choices=PaymentRecord.PaymentMethod.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    reference = forms.CharField(
        label="Referência manual",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    idempotency_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput())

    def __init__(self, *args, billings=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.billings = list(billings)
        for billing in self.billings:
            self.fields[f"allocation_{billing.pk}"] = forms.DecimalField(
                label=billing.description,
                required=False,
                min_value=0,
                max_value=billing.outstanding_value,
                decimal_places=2,
                widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            )

    @property
    def allocations(self):
        return [
            {"billing_id": billing.pk, "amount": self.cleaned_data.get(f"allocation_{billing.pk}")}
            for billing in self.billings
            if self.cleaned_data.get(f"allocation_{billing.pk}")
        ]

    def clean(self):
        cleaned = super().clean()
        selected = [
            cleaned.get(f"allocation_{billing.pk}")
            for billing in self.billings
            if cleaned.get(f"allocation_{billing.pk}")
        ]
        if not selected:
            raise forms.ValidationError("Distribua um valor em ao menos uma cobrança.")
        return cleaned


class PaymentReversalForm(forms.Form):
    reason = forms.CharField(
        label="Motivo do estorno",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )


class CollectionReminderPolicyForm(forms.ModelForm):
    offset_days_text = forms.CharField(
        label="Regras em dias",
        help_text="Separe por vírgulas. Negativo = antes; positivo = depois.",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "-5, 0, 3"}),
    )
    channels = forms.MultipleChoiceField(
        label="Canais",
        choices=(("IN_APP", "Notificação interna"), ("EMAIL", "E-mail")),
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = CollectionReminderPolicy
        fields = ["name", "enabled", "channels"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["offset_days_text"].initial = ", ".join(
                str(value) for value in self.instance.offset_days
            )

    def clean_offset_days_text(self):
        raw = self.cleaned_data["offset_days_text"]
        try:
            return sorted({int(value.strip()) for value in raw.split(",") if value.strip()})
        except ValueError as exc:
            raise DjangoValidationError(
                "Informe somente dias inteiros separados por vírgula."
            ) from exc
