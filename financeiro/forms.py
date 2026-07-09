"""Formularios do modulo Financeiro Escolar."""

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError

from financeiro.models import FinancialPlan, PaymentRecord


class FinancialPlanForm(forms.ModelForm):
    """Formulario de criacao/edicao de plano financeiro."""

    class Meta:
        model = FinancialPlan
        fields = [
            "student",
            "class_obj",
            "academic_year",
            "name",
            "billing_frequency",
            "installment_count",
            "installment_value",
            "due_day",
            "discount_value",
            "late_fee_percent",
            "daily_interest_percent",
            "notes",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-select"}),
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
            "class_obj": "Turma",
            "academic_year": "Ano Letivo",
            "name": "Nome do Plano",
            "billing_frequency": "Frequencia de Cobranca",
            "installment_count": "Numero de Parcelas",
            "installment_value": "Valor da Parcela",
            "due_day": "Dia de Vencimento",
            "discount_value": "Desconto por Parcela",
            "late_fee_percent": "Multa por Atraso (%)",
            "daily_interest_percent": "Juros Diarios (%)",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_obj"].required = False
        self.fields["discount_value"].required = False
        self.fields["late_fee_percent"].required = False
        self.fields["daily_interest_percent"].required = False
        self.fields["notes"].required = False


class GenerateBillingsByClassForm(forms.Form):
    """Formulario para gerar cobrancas em lote por turma e competencia."""

    class_obj = forms.ChoiceField(
        label="Turma",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    academic_year = forms.IntegerField(
        label="Ano Letivo",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 2000, "max": 2100}),
    )
    month = forms.ChoiceField(
        label="Competencia (Mes)",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from classes.selectors import ClassSelector

        classes = ClassSelector().list_ordered()
        self.fields["class_obj"].choices = [
            ("", "---"),
            *[(str(c.pk), str(c)) for c in classes],
        ]
        self.fields["month"].choices = [("", "Mes corrente")] + [
            (str(m), f"{m:02d}") for m in range(1, 13)
        ]


class PaymentForm(forms.ModelForm):
    """Formulario de baixa manual de pagamento."""

    class Meta:
        model = PaymentRecord
        fields = ["amount", "paid_date", "payment_method", "notes"]
        widgets = {
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
            ),
            "paid_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "payment_method": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
        labels = {
            "amount": "Valor Pago",
            "paid_date": "Data de Pagamento",
            "payment_method": "Forma de Pagamento",
            "notes": "Observacoes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notes"].required = False


class RenegotiationForm(forms.Form):
    """Formulario de renegociacao simples de cobranca."""

    new_due_date = forms.DateField(
        label="Novo Vencimento (1a parcela)",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    new_value = forms.DecimalField(
        label="Valor Renegociado (total)",
        required=False,
        min_value=0,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
    )
    installment_count = forms.IntegerField(
        label="Numero de Parcelas",
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
    """Formulario de cancelamento de cobranca."""

    reason = forms.CharField(
        label="Motivo do Cancelamento",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class ReportFilterForm(forms.Form):
    """Filtro para o relatorio mensal previsto x recebido."""

    year = forms.IntegerField(
        label="Ano",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 2000, "max": 2100}),
    )
    month = forms.ChoiceField(
        label="Mes",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["month"].choices = [("", "Ano inteiro")] + [
            (str(m), f"{m:02d}") for m in range(1, 13)
        ]
