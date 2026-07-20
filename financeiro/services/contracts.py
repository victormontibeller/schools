"""Ciclo de vida de contratos financeiros e sua agenda de cobranças."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import service_command
from financeiro.services.rules import ZERO


class ContractLifecycleMixin:
    """Criação, ativação, aditivos e materialização de contratos."""

    @service_command
    def create_contract(self, data: dict):
        """Cria um contrato em rascunho, copiando os termos do modelo."""
        return self._create_contract(data)

    def _create_contract(self, data: dict):
        from classes.contracts import Class
        from financeiro.models import FinancialPlanTemplate, StudentFinancialContract
        from students.contracts import Student

        payload = data.copy()
        template = None
        if payload.get("template_id"):
            try:
                template = FinancialPlanTemplate.objects.get(pk=payload["template_id"])
            except FinancialPlanTemplate.DoesNotExist:
                raise ObjectNotFoundError(
                    "FinancialPlanTemplate", str(payload["template_id"])
                ) from None
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
            ):
                payload.setdefault(field, getattr(template, field))

        self.validate_required(
            payload,
            [
                "student_id",
                "academic_year",
                "name",
                "installment_count",
                "installment_value",
                "due_day",
            ],
        )
        try:
            student = Student.objects.get(pk=payload["student_id"])
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(payload["student_id"])) from None

        class_obj = None
        if payload.get("class_obj_id"):
            try:
                class_obj = Class.objects.get(pk=payload["class_obj_id"])
            except Class.DoesNotExist:
                raise ObjectNotFoundError("Class", str(payload["class_obj_id"])) from None

        values = self._validated_contract_values(payload)
        if StudentFinancialContract.objects.filter(
            student=student,
            academic_year=values["academic_year"],
            status__in=(
                StudentFinancialContract.Status.DRAFT,
                StudentFinancialContract.Status.ACTIVE,
                StudentFinancialContract.Status.SUSPENDED,
            ),
        ).exists():
            raise BusinessRuleViolationError(
                "Já existe um contrato financeiro atual para este aluno e ano letivo."
            )
        start = payload.get("start_competency") or date(values["academic_year"], 1, 1)
        start = start.replace(day=1)
        end = self._add_months(
            start,
            (values["installment_count"] - 1) * self._month_step(values["billing_frequency"]),
        )
        contract = StudentFinancialContract.objects.create(
            template=template,
            student=student,
            class_obj=class_obj,
            start_competency=start,
            end_competency=end,
            status=StudentFinancialContract.Status.DRAFT,
            notes=str(payload.get("notes", "")).strip(),
            **values,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", contract)
        self._log(
            "financial_contract_created",
            contract_id=str(contract.pk),
            student_id=str(student.pk),
            academic_year=contract.academic_year,
        )
        return contract

    @service_command
    def activate_contract(self, contract_id):
        """Ativa e materializa atomicamente todo o calendário do contrato."""
        from financeiro.models import StudentFinancialContract

        try:
            contract = StudentFinancialContract.objects.select_for_update().get(pk=contract_id)
        except StudentFinancialContract.DoesNotExist:
            raise ObjectNotFoundError("StudentFinancialContract", str(contract_id)) from None
        if contract.status != StudentFinancialContract.Status.DRAFT:
            raise BusinessRuleViolationError("Apenas contratos em rascunho podem ser ativados.")
        old_status = contract.status
        contract.status = StudentFinancialContract.Status.ACTIVE
        contract.updated_by = self.user
        contract.save(update_fields=["status", "updated_by", "updated_at", "version"])
        self._record_audit("UPDATE", contract, old_values={"status": old_status})
        created = self._materialize_billings(contract)
        self._log(
            "financial_contract_activated",
            contract_id=str(contract.pk),
            created_count=created,
        )
        return contract

    @service_command
    def update_contract_draft(self, contract_id, data: dict):
        """Edita o snapshot apenas enquanto o contrato permanece em rascunho."""
        from financeiro.models import StudentFinancialContract

        try:
            contract = StudentFinancialContract.objects.select_for_update().get(pk=contract_id)
        except StudentFinancialContract.DoesNotExist:
            raise ObjectNotFoundError("StudentFinancialContract", str(contract_id)) from None
        if contract.status != StudentFinancialContract.Status.DRAFT:
            raise BusinessRuleViolationError("Contrato ativo só pode mudar por aditivo futuro.")
        merged = {
            field: data.get(field, getattr(contract, field))
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
        values = self._validated_contract_values(merged)
        old = self._snapshot(contract, list(values) + ["start_competency", "end_competency"])
        start = data.get("start_competency") or contract.start_competency
        start = start.replace(day=1)
        end = self._add_months(
            start,
            (values["installment_count"] - 1) * self._month_step(values["billing_frequency"]),
        )
        for field, value in values.items():
            setattr(contract, field, value)
        contract.start_competency = start
        contract.end_competency = end
        contract.class_obj_id = data.get("class_obj_id", contract.class_obj_id)
        contract.notes = str(data.get("notes", contract.notes)).strip()
        contract.updated_by = self.user
        contract.save()
        self._record_audit("UPDATE", contract, old_values=old)
        self._log("financial_contract_draft_updated", contract_id=str(contract.pk))
        return contract

    @service_command
    def materialize_contract_billings(self, contract_id) -> int:
        """Materializa parcelas faltantes de modo idempotente."""
        from financeiro.models import StudentFinancialContract

        contract = self._get_contract(contract_id)
        if contract.status != StudentFinancialContract.Status.ACTIVE:
            raise BusinessRuleViolationError("Apenas contratos ativos geram cobranças.")
        return self._materialize_billings(contract)

    def _materialize_billings(self, contract, *, amendment=None) -> int:
        from financeiro.models import BillingEntry

        if contract.installment_value - contract.discount_value <= ZERO:
            raise ValidationError(
                errors={"discount_value": ["O desconto não pode zerar a parcela."]}
            )
        start = contract.start_competency or date(contract.academic_year, 1, 1)
        step = self._month_step(contract.billing_frequency)
        created = 0
        for number in range(1, contract.installment_count + 1):
            if BillingEntry.all_objects.filter(
                contract=contract,
                installment_number=number,
                schedule_revision=contract.terms_revision,
            ).exists():
                continue
            competency = self._add_months(start, (number - 1) * step)
            billing = BillingEntry.objects.create(
                contract=contract,
                amendment=amendment,
                student=contract.student,
                installment_number=number,
                schedule_revision=contract.terms_revision,
                category=BillingEntry.Category.TUITION,
                description=f"{contract.name} - Parcela {number}/{contract.installment_count}",
                principal_value=contract.installment_value,
                discount_value=contract.discount_value,
                competency=competency,
                due_date=competency.replace(day=contract.due_day),
                status=BillingEntry.Status.ACTIVE,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", billing)
            created += 1
        return created

    @service_command
    def materialize_billings_by_class(
        self, class_id, academic_year: int, *, month: int | None = None
    ) -> int:
        """Gera a competência informada para contratos ativos da turma."""
        from classes.contracts import Class
        from financeiro.models import BillingEntry, StudentFinancialContract

        try:
            class_obj = Class.objects.get(pk=class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None
        target = date(academic_year, month or date.today().month, 1)
        created = 0
        contracts = StudentFinancialContract.objects.filter(
            class_obj=class_obj,
            academic_year=academic_year,
            status=StudentFinancialContract.Status.ACTIVE,
            start_competency__lte=target,
            end_competency__gte=target,
        ).select_related("student")
        for contract in contracts:
            step = self._month_step(contract.billing_frequency)
            distance = (target.year - contract.start_competency.year) * 12 + (
                target.month - contract.start_competency.month
            )
            if distance < 0 or distance % step:
                continue
            number = distance // step + 1
            if (
                number > contract.installment_count
                or BillingEntry.all_objects.filter(
                    contract=contract,
                    installment_number=number,
                    schedule_revision=contract.terms_revision,
                ).exists()
            ):
                continue
            billing = BillingEntry.objects.create(
                contract=contract,
                student=contract.student,
                installment_number=number,
                schedule_revision=contract.terms_revision,
                description=f"{contract.name} - Competência {target:%m/%Y}",
                principal_value=contract.installment_value,
                discount_value=contract.discount_value,
                competency=target,
                due_date=target.replace(day=contract.due_day),
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", billing)
            created += 1
        self._log(
            "contract_billings_generated_by_class",
            class_id=str(class_obj.pk),
            academic_year=academic_year,
            competency=target.isoformat(),
            created_count=created,
        )
        return created

    @service_command
    def suspend_contract(self, contract_id, reason: str = ""):
        """Suspende novas materializações sem cancelar cobranças existentes."""
        from financeiro.models import StudentFinancialContract

        contract = self._get_contract(contract_id)
        if contract.status != StudentFinancialContract.Status.ACTIVE:
            raise BusinessRuleViolationError("Apenas contratos ativos podem ser suspensos.")
        old = {"status": contract.status}
        contract.status = StudentFinancialContract.Status.SUSPENDED
        contract.notes = (contract.notes + "\n" + reason.strip()).strip()
        contract.updated_by = self.user
        contract.save()
        self._record_audit("UPDATE", contract, old_values=old)
        self._log("financial_contract_suspended", contract_id=str(contract.pk))
        return contract

    @service_command
    def cancel_contract(self, contract_id, reason: str = ""):
        """Cancela o contrato e suas cobranças futuras ainda sem pagamento."""
        from financeiro.models import BillingEntry, StudentFinancialContract

        contract = self._get_contract(contract_id)
        if contract.status not in (
            StudentFinancialContract.Status.DRAFT,
            StudentFinancialContract.Status.ACTIVE,
            StudentFinancialContract.Status.SUSPENDED,
        ):
            raise BusinessRuleViolationError("Contrato não pode ser cancelado no estado atual.")
        old = {"status": contract.status}
        contract.status = StudentFinancialContract.Status.CANCELLED
        contract.notes = (contract.notes + "\n" + reason.strip()).strip()
        contract.updated_by = self.user
        contract.save()
        self._record_audit("UPDATE", contract, old_values=old)
        for billing in BillingEntry.objects.filter(
            contract=contract,
            paid_value=ZERO,
            status=BillingEntry.Status.ACTIVE,
            competency__gte=date.today().replace(day=1),
        ):
            billing.status = BillingEntry.Status.CANCELLED
            billing.cancelled_reason = reason.strip()
            billing.updated_by = self.user
            billing.save()
            self._record_audit("UPDATE", billing, old_values={"status": "ACTIVE"})
        self._log("financial_contract_cancelled", contract_id=str(contract.pk))
        return contract

    @service_command
    def close_contract(self, contract_id):
        """Encerra o contrato somente quando não houver saldo pendente."""
        from financeiro.models import BillingEntry, StudentFinancialContract

        contract = self._get_contract(contract_id)
        if any(
            billing.outstanding_value > ZERO
            for billing in BillingEntry.objects.filter(contract=contract).exclude(
                status=BillingEntry.Status.CANCELLED
            )
        ):
            raise BusinessRuleViolationError("O contrato ainda possui cobranças em aberto.")
        old = {"status": contract.status}
        contract.status = StudentFinancialContract.Status.CLOSED
        contract.updated_by = self.user
        contract.save()
        self._record_audit("UPDATE", contract, old_values=old)
        self._log("financial_contract_closed", contract_id=str(contract.pk))
        return contract

    def _validated_contract_values(self, data: dict) -> dict:
        count = int(data["installment_count"])
        value = self._to_decimal(data["installment_value"])
        discount = self._to_decimal(data.get("discount_value", 0))
        due_day = int(data["due_day"])
        if count < 1 or count > 60:
            raise ValidationError(errors={"installment_count": ["Informe entre 1 e 60 parcelas."]})
        if value <= ZERO or discount < ZERO or discount >= value:
            raise ValidationError(errors={"installment_value": ["Valores contratuais inválidos."]})
        if due_day < 1 or due_day > 28:
            raise ValidationError(errors={"due_day": ["Informe um dia entre 1 e 28."]})
        return {
            "academic_year": int(data["academic_year"]),
            "name": str(data["name"]).strip(),
            "billing_frequency": data.get("billing_frequency", "MONTHLY"),
            "installment_count": count,
            "installment_value": value,
            "due_day": due_day,
            "discount_value": discount,
            "late_fee_percent": self._to_decimal(data.get("late_fee_percent", 0)),
            "daily_interest_percent": Decimal(str(data.get("daily_interest_percent", 0))).quantize(
                Decimal("0.0001")
            ),
        }

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        absolute = value.year * 12 + value.month - 1 + months
        return date(absolute // 12, absolute % 12 + 1, 1)
