"""Aditivos futuros dos contratos financeiros ativos."""

from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import service_command
from financeiro.services.rules import ZERO


class ContractAmendmentMixin:
    """Substitui somente a agenda futura ainda não paga."""

    @service_command
    def create_amendment(self, contract_id, data: dict):
        from financeiro.models import (
            BillingEntry,
            FinancialContractAmendment,
            StudentFinancialContract,
        )

        self.validate_required(data, ["effective_competency", "reason"])
        try:
            contract = StudentFinancialContract.objects.select_for_update().get(pk=contract_id)
        except StudentFinancialContract.DoesNotExist:
            raise ObjectNotFoundError("StudentFinancialContract", str(contract_id)) from None
        if contract.status != StudentFinancialContract.Status.ACTIVE:
            raise BusinessRuleViolationError("Somente contratos ativos recebem aditivos.")
        allowed = {
            "installment_count",
            "installment_value",
            "discount_value",
            "due_day",
            "late_fee_percent",
            "daily_interest_percent",
        }
        submitted = {
            key: data[key] for key in allowed if key in data and data[key] not in (None, "")
        }
        if not submitted:
            raise ValidationError(errors={"changed_terms": ["Informe ao menos uma alteração."]})
        merged = {
            field: submitted.get(field, getattr(contract, field))
            for field in (
                "academic_year",
                "name",
                "billing_frequency",
                "installment_count",
                "installment_value",
                "due_day",
                "discount_value",
                "late_fee_percent",
                "daily_interest_percent",
            )
        }
        validated = self._validated_contract_values(merged)
        changed = {field: validated[field] for field in submitted}
        effective = data["effective_competency"].replace(day=1)
        if effective <= timezone.localdate().replace(day=1):
            raise ValidationError(errors={"effective_competency": ["A vigência deve ser futura."]})
        if FinancialContractAmendment.objects.filter(
            contract=contract, effective_competency__gt=effective
        ).exists():
            raise ValidationError(
                errors={"effective_competency": ["A vigência não pode preceder o último aditivo."]}
            )
        future = list(
            BillingEntry.objects.select_for_update()
            .filter(contract=contract, competency__gte=effective, renegotiated_from__isnull=True)
            .exclude(status=BillingEntry.Status.CANCELLED)
            .order_by("pk")
        )
        if any(item.paid_value > ZERO for item in future):
            raise BusinessRuleViolationError(
                "Há cobrança futura com pagamento; o aditivo não pode alterar esse período."
            )
        amendment = FinancialContractAmendment.objects.create(
            contract=contract,
            revision=contract.terms_revision + 1,
            effective_competency=effective,
            changed_terms={key: str(value) for key, value in changed.items()},
            reason=str(data["reason"]).strip(),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", amendment)
        old_count = contract.installment_count
        old_start = contract.start_competency
        for field, value in changed.items():
            setattr(contract, field, value)
        contract.end_competency = self._add_months(
            old_start,
            (contract.installment_count - 1) * self._month_step(contract.billing_frequency),
        )
        contract.terms_revision = amendment.revision
        contract.updated_by = self.user
        contract.save()
        self._record_audit(
            "UPDATE", contract, old_values={"terms_revision": amendment.revision - 1}
        )
        for old in future:
            old.status = BillingEntry.Status.CANCELLED
            old.cancelling_amendment = amendment
            old.cancelled_reason = f"Substituída pelo aditivo {amendment.revision}"
            old.updated_by = self.user
            old.save()
            self._record_audit("DELETE", old)
            if old.installment_number > contract.installment_count:
                continue
            self._create_replacement(
                contract,
                amendment,
                number=old.installment_number,
                competency=old.competency,
                category=old.category,
                description=old.description,
            )
        step = self._month_step(contract.billing_frequency)
        for number in range(1, contract.installment_count + 1):
            competency = self._add_months(old_start, (number - 1) * step)
            if competency < effective:
                continue
            previous = (
                BillingEntry.all_objects.filter(
                    contract=contract,
                    installment_number=number,
                    renegotiated_from__isnull=True,
                )
                .order_by("-schedule_revision")
                .first()
            )
            if previous and not (
                number > old_count
                and previous.status == BillingEntry.Status.CANCELLED
                and previous.cancelling_amendment_id
            ):
                continue
            self._create_replacement(
                contract,
                amendment,
                number=number,
                competency=competency,
                category=BillingEntry.Category.TUITION,
                description=f"{contract.name} - Parcela {number}/{contract.installment_count}",
            )
        self._log(
            "financial_contract_amended",
            contract_id=str(contract.pk),
            amendment_id=str(amendment.pk),
            replaced_count=len(future),
        )
        return amendment

    def _create_replacement(
        self, contract, amendment, *, number, competency, category, description
    ):
        from financeiro.models import BillingEntry

        replacement = BillingEntry.objects.create(
            contract=contract,
            amendment=amendment,
            student=contract.student,
            installment_number=number,
            schedule_revision=amendment.revision,
            category=category,
            description=description,
            principal_value=contract.installment_value,
            discount_value=contract.discount_value,
            late_fee_percent=contract.late_fee_percent,
            daily_interest_percent=contract.daily_interest_percent,
            competency=competency,
            due_date=competency.replace(day=contract.due_day),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", replacement)
        return replacement
