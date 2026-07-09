"""FinanceService e PaymentService: regras de negocio do modulo Financeiro Escolar.

- FinanceService: planos, geracao de cobrancas em lote, cancelamento,
  renegociacao com novo vencimento e aplicacao de multa/juros por atraso.
- PaymentService: baixa manual de pagamentos (parcial ou total) e conciliacao basica.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import BaseService

if TYPE_CHECKING:
    from financeiro.models import BillingEntry, FinancialPlan, PaymentRecord

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")


class FinanceService(BaseService):
    """Servico de planos financeiros e geracao de cobrancas."""

    ACTIVE_PLAN_STATUSES = ("ACTIVE",)
    OPEN_LIKE_STATUSES = ("OPEN", "OVERDUE")

    def create_plan(self, data: dict) -> FinancialPlan:
        """Cria um plano financeiro no estado DRAFT."""
        from classes.models import Class
        from financeiro.models import FinancialPlan
        from students.models import Student

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
        from classes.models import Class
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

    @transaction.atomic
    def cancel_billing(self, billing_id, reason: str = "") -> BillingEntry:
        """Cancela uma cobranca em aberto. Proibe cancelar cobranca ja paga."""
        from financeiro.models import BillingEntry

        try:
            billing = BillingEntry.objects.get(pk=billing_id)
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None

        if billing.status == BillingEntry.Status.CANCELLED:
            raise BusinessRuleViolationError("Cobranca ja esta cancelada.")
        if billing.is_settled:
            raise BusinessRuleViolationError("Cobranca quitada nao pode ser cancelada.")

        old_status = billing.status
        billing.status = BillingEntry.Status.CANCELLED
        billing.cancelled_reason = reason.strip()
        billing.updated_by = self.user
        billing.save(
            update_fields=["status", "cancelled_reason", "updated_by", "updated_at", "version"]
        )
        self._record_audit("DELETE", billing, old_values={"status": old_status})
        self._log("Cobranca cancelada", billing_id=str(billing.pk))
        return billing

    @transaction.atomic
    def renegotiate_billing(
        self,
        billing_id,
        *,
        new_due_date: date,
        new_value: Decimal | None = None,
        installment_count: int = 1,
    ) -> list[BillingEntry]:
        """Renegocia uma cobranca em aberto/vencida: cancela a original e cria 1..N novas com
        novo vencimento. Se `new_value` for omitido, usa o saldo devedor atual.

        Returns:
            Lista das novas cobrancas geradas.
        """
        from financeiro.models import BillingEntry

        try:
            billing = BillingEntry.objects.select_related("plan", "student").get(pk=billing_id)
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None

        if billing.status in (BillingEntry.Status.PAID, BillingEntry.Status.CANCELLED):
            raise BusinessRuleViolationError(
                "Cobranca quitada ou cancelada nao pode ser renegociada."
            )

        if not isinstance(new_due_date, date):
            raise ValidationError(errors={"new_due_date": ["Data de vencimento invalida."]})

        outstanding = billing.outstanding_value
        if outstanding <= 0:
            raise BusinessRuleViolationError("Cobranca nao possui saldo devedor para renegociar.")

        renegotiated_value = new_value if new_value is not None else outstanding
        renegotiated_value = self._to_decimal(renegotiated_value)
        if renegotiated_value <= 0:
            raise ValidationError(
                errors={"new_value": ["Valor renegociado deve ser maior que zero."]}
            )

        if installment_count < 1 or installment_count > 12:
            raise ValidationError(
                errors={"installment_count": ["Parcelas devem ser entre 1 e 12."]}
            )

        installment_values = self._split_amount(renegotiated_value, installment_count)

        old_status = billing.status
        billing.status = BillingEntry.Status.CANCELLED
        billing.cancelled_reason = "Renegociacao"
        billing.updated_by = self.user
        billing.save(
            update_fields=["status", "cancelled_reason", "updated_by", "updated_at", "version"]
        )
        self._record_audit("DELETE", billing, old_values={"status": old_status})

        next_installment = self._next_installment_number(billing.plan_id)
        new_billings: list[BillingEntry] = []
        for i, amount in enumerate(installment_values):
            due = new_due_date + timedelta(days=30 * i)
            nb = BillingEntry.objects.create(
                plan=billing.plan,
                student=billing.student,
                installment_number=next_installment + i,
                description=f"Renegociacao — {billing.description} "
                f"(Parcela {i + 1}/{installment_count})",
                original_value=amount,
                discount_value=ZERO,
                paid_value=ZERO,
                due_date=due,
                status=BillingEntry.Status.OPEN,
                renegotiated_from=billing,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", nb)
            new_billings.append(nb)

        self._log(
            "Cobranca renegociada",
            billing_id=str(billing.pk),
            new_count=installment_count,
            new_value=str(renegotiated_value),
        )
        return new_billings

    def apply_late_fees(self, billing_id, *, reference_date: date | None = None) -> BillingEntry:
        """Aplica multa e juros de mora a uma cobranca vencida, recalculando o valor original.

        A multa e juros sao acrescentados ao `original_value`, preservando
        o `discount_value`. Idempotente: se ja aplicado (flag em `notes`), nao reaplica.
        """
        from financeiro.models import BillingEntry

        try:
            billing = BillingEntry.objects.get(pk=billing_id)
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None

        if billing.status != BillingEntry.Status.OVERDUE:
            raise BusinessRuleViolationError(
                "Apenas cobrancas vencidas podem ter multa e juros aplicados."
            )

        if "[multa-aplicada]" in billing.notes:
            return billing

        plan = billing.plan
        reference = reference_date or date.today()
        days_late = (reference - billing.due_date).days
        if days_late <= 0:
            raise BusinessRuleViolationError(
                "Cobranca nao esta em atraso em relacao a data informada."
            )

        late_fee = (billing.original_value * plan.late_fee_percent / Decimal("100")).quantize(
            Decimal("0.01")
        )
        interest = (
            billing.original_value
            * plan.daily_interest_percent
            * Decimal(days_late)
            / Decimal("100")
        ).quantize(Decimal("0.01"))

        old_values = {
            "original_value": str(billing.original_value),
            "notes": billing.notes,
            "version": billing.version,
        }
        billing.original_value = billing.original_value + late_fee + interest
        billing.notes = (
            (billing.notes or "")
            + f"\n[multa-aplicada] dias={days_late} multa={late_fee} \
juros={interest}"
        )
        billing.updated_by = self.user
        billing.save(
            update_fields=["original_value", "notes", "updated_by", "updated_at", "version"]
        )
        self._record_audit("UPDATE", billing, old_values=old_values)
        self._log(
            "Multa e juros aplicados",
            billing_id=str(billing.pk),
            days_late=days_late,
            late_fee=str(late_fee),
            interest=str(interest),
        )
        return billing

    def refresh_overdue_status(self, *, reference_date: date | None = None) -> int:
        """Varredura que marca cobrancas OPEN vencidas como OVERDUE. Operacao para scheduler.

        Returns:
            Quantidade de cobrancas atualizadas.
        """
        from financeiro.models import BillingEntry

        reference = reference_date or date.today()
        qs = BillingEntry.objects.filter(status=BillingEntry.Status.OPEN, due_date__lt=reference)
        count = 0
        for billing in qs:
            old_status = billing.status
            billing.status = BillingEntry.Status.OVERDUE
            billing.updated_by = self.user
            billing.save(update_fields=["status", "updated_by", "updated_at", "version"])
            self._record_audit("UPDATE", billing, old_values={"status": old_status})
            count += 1
        if count:
            self._log(
                "Status vencido atualizado em lote", updated_count=count, reference=str(reference)
            )
        return count

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_plan(self, plan_id) -> FinancialPlan:
        from financeiro.models import FinancialPlan

        try:
            return FinancialPlan.objects.select_related("student", "class_obj").get(pk=plan_id)
        except FinancialPlan.DoesNotExist:
            raise ObjectNotFoundError("FinancialPlan", str(plan_id)) from None

    @staticmethod
    def _to_decimal(value, default: Decimal = ZERO) -> Decimal:
        if value in (None, ""):
            return default
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except (ArithmeticError, ValueError):
            raise ValidationError(errors={"value": ["Valor monetario invalido."]}) from None

    @staticmethod
    def _month_step(frequency: str) -> int:
        return {
            "MONTHLY": 1,
            "BIMONTHLY": 2,
            "QUARTERLY": 3,
            "ANNUAL": 12,
        }.get(frequency, 1)

    @staticmethod
    def _normalize_month(year: int, month: int) -> tuple[int, int]:
        """Normaliza month > 12 rolando para o ano seguinte."""
        while month > 12:
            month -= 12
            year += 1
        return year, month

    @staticmethod
    def _installment_for_month(plan, month: int) -> int | None:
        """Calcula o numero da parcela esperada para o mes (1-based) ou None."""
        step = FinanceService._month_step(plan.billing_frequency)
        if step == 0:
            return None
        index = (month - 1) // step + 1
        if index > plan.installment_count:
            return None
        return index

    @staticmethod
    def _next_installment_number(plan_id) -> int:
        from django.db.models import Max

        from financeiro.models import BillingEntry

        current = (
            BillingEntry.all_objects.filter(plan_id=plan_id).aggregate(
                max_number=Max("installment_number")
            )["max_number"]
            or 0
        )
        return current + 1

    @staticmethod
    def _split_amount(amount: Decimal, installment_count: int) -> list[Decimal]:
        """Divide um valor em parcelas sem perder centavos."""
        total_cents = int((amount * Decimal("100")).to_integral_value())
        base_cents, remainder = divmod(total_cents, installment_count)
        values = [Decimal(base_cents) / Decimal("100") for _ in range(installment_count)]
        values[-1] += Decimal(remainder) / Decimal("100")
        return values


class PaymentService(BaseService):
    """Servico de baixa manual de pagamentos e conciliacao."""

    @transaction.atomic
    def register_payment(
        self,
        billing_id,
        *,
        amount,
        paid_date: date,
        payment_method="CASH",
        notes: str = "",
    ) -> PaymentRecord:
        """Registra um pagamento (parcial ou total) e recalcula o status da cobranca."""
        from financeiro.models import BillingEntry, PaymentRecord

        try:
            billing = BillingEntry.objects.select_for_update().get(pk=billing_id)
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None

        if billing.status in (BillingEntry.Status.CANCELLED, BillingEntry.Status.PAID):
            raise BusinessRuleViolationError(
                "Cobranca cancelada ou ja quitada nao pode receber pagamento."
            )

        value = FinanceService._to_decimal(amount)
        if value <= 0:
            raise ValidationError(
                errors={"amount": ["Valor do pagamento deve ser maior que zero."]}
            )

        if value > billing.outstanding_value:
            raise ValidationError(
                errors={"amount": ["Valor do pagamento excede o saldo da cobranca."]}
            )

        if self._is_future(paid_date):
            raise ValidationError(errors={"paid_date": ["Data de pagamento nao pode ser futura."]})

        payment = PaymentRecord.objects.create(
            billing=billing,
            amount=value,
            paid_date=paid_date,
            payment_method=payment_method,
            received_by=self.user,
            notes=notes.strip(),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", payment)

        billing.paid_value = (billing.paid_value or ZERO) + value
        old_status = billing.status
        new_status = billing.computed_status()
        billing.status = new_status
        billing.updated_by = self.user
        billing.save(update_fields=["paid_value", "status", "updated_by", "updated_at", "version"])
        if old_status != new_status:
            self._record_audit("UPDATE", billing, old_values={"status": old_status})

        self._log(
            "Pagamento registrado",
            billing_id=str(billing.pk),
            payment_id=str(payment.pk),
            amount=str(value),
            new_status=new_status,
        )
        return payment

    @transaction.atomic
    def reconcile(self, payment_id, *, confirmed: bool = True) -> PaymentRecord:
        """Conciliacao basica: marca/invalida um pagamento. Em caso de invalidacao,
        estorna o valor pago da cobranca e recoloca o status correto.
        """
        from financeiro.models import BillingEntry, PaymentRecord

        try:
            payment = PaymentRecord.objects.select_related("billing").get(pk=payment_id)
        except PaymentRecord.DoesNotExist:
            raise ObjectNotFoundError("PaymentRecord", str(payment_id)) from None

        if payment.reconciliation_status == PaymentRecord.ReconciliationStatus.REJECTED:
            raise BusinessRuleViolationError(
                "Pagamento estornado nao pode ser conciliado novamente."
            )

        if not confirmed:
            billing = BillingEntry.objects.select_for_update().get(pk=payment.billing_id)
            old_paid = billing.paid_value
            old_status = billing.status
            billing.paid_value = max((billing.paid_value or ZERO) - payment.amount, ZERO)
            billing.status = billing.computed_status()
            billing.updated_by = self.user
            billing.save(
                update_fields=["paid_value", "status", "updated_by", "updated_at", "version"]
            )
            old_payment_status = payment.reconciliation_status
            payment.reconciliation_status = PaymentRecord.ReconciliationStatus.REJECTED
            payment.updated_by = self.user
            payment.save(
                update_fields=[
                    "reconciliation_status",
                    "updated_by",
                    "updated_at",
                    "version",
                ]
            )
            payment.soft_delete(user=self.user)
            self._record_audit(
                "DELETE",
                payment,
                old_values={"reconciliation_status": old_payment_status},
            )
            if old_status != billing.status:
                self._record_audit(
                    "UPDATE",
                    billing,
                    old_values={"status": old_status, "paid_value": str(old_paid)},
                )
            self._log(
                "Pagamento estornado (conciliacao)",
                billing_id=str(billing.pk),
                payment_id=str(payment.pk),
            )
        else:
            if payment.reconciliation_status == PaymentRecord.ReconciliationStatus.CONFIRMED:
                return payment
            old_status = payment.reconciliation_status
            payment.reconciliation_status = PaymentRecord.ReconciliationStatus.CONFIRMED
            payment.reconciled_at = timezone.now()
            payment.updated_by = self.user
            payment.save(
                update_fields=[
                    "reconciliation_status",
                    "reconciled_at",
                    "updated_by",
                    "updated_at",
                    "version",
                ]
            )
            self._record_audit("UPDATE", payment, old_values={"reconciliation_status": old_status})
            self._log(
                "Pagamento conciliado",
                billing_id=str(payment.billing_id),
                payment_id=str(payment.pk),
            )
        return payment

    @staticmethod
    def _is_future(target: date) -> bool:
        return target > date.today()
