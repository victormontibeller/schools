"""Ciclo de vida dos modelos reutilizáveis de plano financeiro."""

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
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
