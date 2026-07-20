"""Ciclo de vida dos modelos reutilizáveis de plano financeiro."""

from decimal import Decimal

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import service_command


class TemplateLifecycleMixin:
    """Comandos de criação, edição e desativação de modelos de plano."""

    @service_command
    def create_financial_template(self, data: dict):
        """Cria um modelo reutilizável sem alterar contratos existentes."""
        from financeiro.models import FinancialPlanTemplate

        self.validate_required(
            data,
            [
                "name",
                "academic_year",
                "installment_count",
                "installment_value",
                "due_day",
            ],
        )
        values = self._validated_template_values(data)
        if FinancialPlanTemplate.objects.filter(
            name__iexact=values["name"], academic_year=values["academic_year"]
        ).exists():
            raise BusinessRuleViolationError(
                "Já existe um modelo ativo com este nome e ano letivo."
            )
        template = FinancialPlanTemplate.objects.create(
            **values,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", template)
        self._log(
            "financial_template_created",
            template_id=str(template.pk),
            academic_year=template.academic_year,
        )
        return template

    @service_command
    def update_financial_template(self, template_id, data: dict):
        """Atualiza um modelo para uso apenas em contratos criados posteriormente."""
        from financeiro.models import FinancialPlanTemplate

        try:
            template = FinancialPlanTemplate.objects.get(pk=template_id)
        except FinancialPlanTemplate.DoesNotExist:
            raise ObjectNotFoundError("FinancialPlanTemplate", str(template_id)) from None

        merged = {
            field: data.get(field, getattr(template, field))
            for field in (
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
            )
        }
        values = self._validated_template_values(merged)
        duplicate = FinancialPlanTemplate.objects.filter(
            name__iexact=values["name"], academic_year=values["academic_year"]
        ).exclude(pk=template.pk)
        if duplicate.exists():
            raise BusinessRuleViolationError(
                "Já existe um modelo ativo com este nome e ano letivo."
            )

        old = self._snapshot(template, list(values))
        repo = BaseRepository()
        repo.model_class = FinancialPlanTemplate
        template = repo.update(
            template,
            expected_version=data.get("version", template.version),
            **values,
            updated_by=self.user,
        )
        self._record_audit("UPDATE", template, old_values=old)
        self._log("financial_template_updated", template_id=str(template.pk))
        return template

    @service_command
    def deactivate_financial_template(self, template_id):
        """Desativa o modelo sem afetar snapshots contratuais."""
        from financeiro.models import FinancialPlanTemplate

        return self._deactivate(FinancialPlanTemplate, template_id, "FinancialPlanTemplate")

    def _validated_template_values(self, data: dict) -> dict:
        from financeiro.models import StudentFinancialContract

        count = int(data["installment_count"])
        due_day = int(data["due_day"])
        value = self._to_decimal(data["installment_value"])
        discount = self._to_decimal(data.get("discount_value", 0))
        late_fee = self._to_decimal(data.get("late_fee_percent", 0))
        interest = Decimal(str(data.get("daily_interest_percent", 0))).quantize(Decimal("0.0001"))
        if count < 1 or count > 60:
            raise ValidationError(errors={"installment_count": ["Informe entre 1 e 60 parcelas."]})
        if due_day < 1 or due_day > 28:
            raise ValidationError(errors={"due_day": ["Informe um dia entre 1 e 28."]})
        if value <= 0:
            raise ValidationError(errors={"installment_value": ["O valor deve ser positivo."]})
        if discount < 0 or discount >= value:
            raise ValidationError(
                errors={"discount_value": ["O desconto deve ser menor que o valor da parcela."]}
            )
        if late_fee < 0 or interest < 0:
            raise ValidationError(
                errors={"late_fee_percent": ["Encargos não podem ser negativos."]}
            )
        frequency = data.get("billing_frequency", StudentFinancialContract.BillingFrequency.MONTHLY)
        if frequency not in StudentFinancialContract.BillingFrequency.values:
            raise ValidationError(errors={"billing_frequency": ["Frequência inválida."]})
        return {
            "name": str(data["name"]).strip(),
            "academic_year": int(data["academic_year"]),
            "billing_frequency": frequency,
            "installment_count": count,
            "installment_value": value,
            "due_day": due_day,
            "discount_value": discount,
            "late_fee_percent": late_fee,
            "daily_interest_percent": interest,
            "description": str(data.get("description", "")).strip(),
        }
