"""Ciclo de vida e geração de planos financeiros."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from financeiro.services.rules import ZERO

if TYPE_CHECKING:
    from financeiro.models import FinancialPlan


class PlanLifecycleMixin:
    """Criação, ativação, suspensão e geração de cobranças de planos."""

    def create_plan(self, data: dict) -> FinancialPlan:
        """Cria um plano financeiro no estado DRAFT."""
        from classes.contracts import Class
        from financeiro.models import FinancialPlan
        from students.contracts import Student

        self.validate_required(
            data,
            [
                "student_id",
                "academic_year",
                "name",
                "installment_count",
                "installment_value",
                "due_day",
            ],
        )

        student_id = data["student_id"]
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(student_id)) from None

        class_obj = None
        if data.get("class_obj_id"):
            try:
                class_obj = Class.objects.get(pk=data["class_obj_id"])
            except Class.DoesNotExist:
                raise ObjectNotFoundError("Class", str(data["class_obj_id"])) from None

        installment_count = int(data["installment_count"])
        if installment_count <= 0 or installment_count > 60:
            raise ValidationError(
                errors={"installment_count": ["Numero de parcelas deve ser entre 1 e 60."]}
            )

        installment_value = self._to_decimal(data["installment_value"])
        if installment_value <= 0:
            raise ValidationError(
                errors={"installment_value": ["Valor da parcela deve ser maior que zero."]}
            )

        due_day = int(data["due_day"])
        if due_day < 1 or due_day > 28:
            raise ValidationError(errors={"due_day": ["Dia de vencimento deve ser entre 1 e 28."]})

        discount_value = self._to_decimal(data.get("discount_value", 0))
        if discount_value < 0:
            raise ValidationError(errors={"discount_value": ["Desconto nao pode ser negativo."]})

        late_fee_percent = self._to_decimal(data.get("late_fee_percent", 0))
        daily_interest_percent = self._to_decimal(data.get("daily_interest_percent", 0))

        academic_year = int(data["academic_year"])

        class_obj_id = class_obj.pk if class_obj else None
        if FinancialPlan.objects.filter(
            student=student,
            academic_year=academic_year,
            status__in=self.ACTIVE_PLAN_STATUSES + ("DRAFT",),
        ).exists():
            raise BusinessRuleViolationError(
                "Ja existe um plano financeiro ativo ou em rascunho para este aluno e ano letivo."
            )

        plan = FinancialPlan.objects.create(
            student=student,
            class_obj=class_obj,
            academic_year=academic_year,
            name=data["name"].strip(),
            status=FinancialPlan.Status.DRAFT,
            billing_frequency=data.get("billing_frequency", FinancialPlan.BillingFrequency.MONTHLY),
            installment_count=installment_count,
            installment_value=installment_value,
            due_day=due_day,
            discount_value=discount_value,
            late_fee_percent=late_fee_percent,
            daily_interest_percent=daily_interest_percent,
            notes=data.get("notes", ""),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", plan)
        self._log(
            "Plano financeiro criado",
            plan_id=str(plan.pk),
            student_id=str(student.pk),
            class_id=str(class_obj_id) if class_obj_id else "",
            academic_year=academic_year,
        )
        return plan

    def activate_plan(self, plan_id) -> FinancialPlan:
        """Ativa um plano em rascunho, liberando a geracao de cobrancas."""
        from financeiro.models import FinancialPlan

        plan = self._get_plan(plan_id)
        if plan.status != FinancialPlan.Status.DRAFT:
            raise BusinessRuleViolationError("Apenas planos em rascunho podem ser ativados.")

        old_status = plan.status
        plan.status = FinancialPlan.Status.ACTIVE
        plan.updated_by = self.user
        plan.save(update_fields=["status", "updated_by", "updated_at", "version"])
        self._record_audit("UPDATE", plan, old_values={"status": old_status})
        self._log("Plano financeiro ativado", plan_id=str(plan.pk))
        return plan

    @transaction.atomic
    def generate_billings(self, plan_id) -> int:
        """Gera as cobrancas de um plano ativo a partir da frequencia e parcelas.

        Returns:
            Quantidade de cobrancas criadas (ignora ja existentes).
        """
        from financeiro.models import BillingEntry, FinancialPlan

        plan = self._get_plan(plan_id)
        if plan.status != FinancialPlan.Status.ACTIVE:
            raise BusinessRuleViolationError("Apenas planos ativos podem gerar cobrancas.")

        if BillingEntry.objects.filter(plan=plan).exists():
            raise BusinessRuleViolationError("Cobrancas ja foram geradas para este plano.")

        net_value = (plan.installment_value - plan.discount_value).quantize(Decimal("0.01"))
        if net_value <= 0:
            raise ValidationError(
                errors={"discount_value": ["Desconto nao pode zerar o valor da parcela."]}
            )

        month_step = self._month_step(plan.billing_frequency)
        created = 0
        year = plan.academic_year
        for installment in range(1, plan.installment_count + 1):
            due_month = 1 + (installment - 1) * month_step
            due_year, due_month = self._normalize_month(year, due_month)
            due = date(due_year, due_month, plan.due_day)
            billing = BillingEntry.objects.create(
                plan=plan,
                student=plan.student,
                installment_number=installment,
                description=f"{plan.name} — Parcela {installment}/{plan.installment_count}",
                original_value=plan.installment_value,
                discount_value=plan.discount_value,
                paid_value=ZERO,
                due_date=due,
                status=BillingEntry.Status.OPEN,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", billing)
            created += 1

        self._log(
            "Cobrancas geradas para plano",
            plan_id=str(plan.pk),
            created_count=created,
        )
        return created

    @transaction.atomic
    def generate_billings_by_class(
        self, class_id, academic_year: int, *, month: int | None = None
    ) -> int:
        """Gera em lote as cobrancas do mes/competencia para todos os alunos ativos de uma turma.

        Args:
            class_id: turma alvo.
            academic_year: ano letivo.
            month: mes da competencia. Se None, usa o mes corrente.

        Returns:
            Quantidade de cobrancas criadas.
        """
        from classes.contracts import Class
        from financeiro.models import BillingEntry, FinancialPlan

        try:
            class_obj = Class.objects.get(pk=class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None

        target_month = month or date.today().month
        due_year, due_month = self._normalize_month(academic_year, target_month)

        plans = FinancialPlan.objects.filter(
            class_obj=class_obj,
            academic_year=academic_year,
            status=FinancialPlan.Status.ACTIVE,
        ).select_related("student")

        created = 0
        for plan in plans:
            installment = self._installment_for_month(plan, target_month)
            if installment is None:
                continue
            if BillingEntry.objects.filter(plan=plan, installment_number=installment).exists():
                continue
            due = date(due_year, due_month, plan.due_day)
            billing = BillingEntry.objects.create(
                plan=plan,
                student=plan.student,
                installment_number=installment,
                description=f"{plan.name} — Competencia {due_month:02d}/{due_year} "
                f"(Parcela {installment}/{plan.installment_count})",
                original_value=plan.installment_value,
                discount_value=plan.discount_value,
                paid_value=ZERO,
                due_date=due,
                status=BillingEntry.Status.OPEN,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", billing)
            created += 1

        self._log(
            "Cobrancas em lote geradas por turma",
            class_id=str(class_obj.pk),
            academic_year=academic_year,
            month=str(target_month),
            created_count=created,
        )
        return created

    def cancel_plan(self, plan_id, reason: str = "") -> FinancialPlan:
        """Suspende um plano ativo, impedindo novas cobrancas. Cobrancas em aberto permanecem."""
        from financeiro.models import FinancialPlan

        plan = self._get_plan(plan_id)
        if plan.status not in (FinancialPlan.Status.ACTIVE, FinancialPlan.Status.SUSPENDED):
            raise BusinessRuleViolationError("Plano nao pode ser cancelado no estado atual.")

        old_status = plan.status
        plan.status = FinancialPlan.Status.SUSPENDED
        plan.notes = (plan.notes + "\n" + reason.strip()).strip() if reason.strip() else plan.notes
        plan.updated_by = self.user
        plan.save(update_fields=["status", "notes", "updated_by", "updated_at", "version"])
        self._record_audit("UPDATE", plan, old_values={"status": old_status})
        self._log("Plano financeiro suspenso", plan_id=str(plan.pk))
        return plan
