"""Seed idempotente do cenário financeiro completo do tenant DEMO."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from django.db import IntegrityError
from django.utils import timezone

from base.services import system_command


class FinanceDemoSeedMixin:
    """Materializa o fluxo demonstrativo usando somente comandos públicos financeiros."""

    _PAYMENT_NAMESPACE = "school-manager/demo/finance"

    @system_command
    def populate_finance(self) -> dict[str, int]:
        """Cria planos, contratos, cobranças e baixas financeiras demonstrativas.

        As competências são sempre relativas à data atual. Registros financeiros históricos já
        criados não são recriados nem têm suas transições repetidas em uma nova execução.
        """
        from financeiro.models import (
            BillingEntry,
            CollectionReminderPolicy,
            FinancialContractAmendment,
            FinancialPlanTemplate,
            PaymentRecord,
            StudentFinancialContract,
        )
        from financeiro.services import FinanceService, PaymentService
        from students.contracts import Student

        today = timezone.localdate()
        academic_year = today.year
        month_start = today.replace(day=1)
        finance_service = FinanceService(user=self.user)
        payment_service = PaymentService(user=self.user)

        templates = {
            key: self._ensure_financial_template(
                finance_service,
                FinancialPlanTemplate,
                academic_year,
                **data,
            )
            for key, data in {
                "fundamental": {
                    "name": "Plano Fundamental DEMO",
                    "installment_count": 12,
                    "installment_value": Decimal("1250.00"),
                    "discount_value": Decimal("50.00"),
                    "due_day": 10,
                    "late_fee_percent": Decimal("2.00"),
                    "daily_interest_percent": Decimal("0.1000"),
                    "description": "Plano anual demonstrativo do Ensino Fundamental.",
                },
                "infantil": {
                    "name": "Plano Infantil DEMO",
                    "installment_count": 12,
                    "installment_value": Decimal("980.00"),
                    "discount_value": Decimal("30.00"),
                    "due_day": 8,
                    "late_fee_percent": Decimal("2.00"),
                    "daily_interest_percent": Decimal("0.1000"),
                    "description": "Plano anual demonstrativo da Educação Infantil.",
                },
                "contraturno": {
                    "name": "Plano Contraturno DEMO",
                    "installment_count": 12,
                    "installment_value": Decimal("420.00"),
                    "discount_value": Decimal("0.00"),
                    "due_day": 12,
                    "late_fee_percent": Decimal("1.00"),
                    "daily_interest_percent": Decimal("0.0500"),
                    "description": "Plano anual demonstrativo de atividades no contraturno.",
                },
            }.items()
        }
        students = {
            enrollment: Student.objects.get(enrollment_number=enrollment)
            for enrollment in (
                "2026001",
                "2026002",
                "2026003",
                "2026004",
                "2026005",
                "2026006",
                "2026007",
            )
        }
        start_competency = self._add_months(month_start, -3)
        contracts = {
            "movements": self._ensure_financial_contract(
                finance_service,
                StudentFinancialContract,
                student=students["2026001"],
                template=templates["fundamental"],
                academic_year=academic_year,
                name="Contrato DEMO - Movimentações",
                start_competency=start_competency,
                target_status=StudentFinancialContract.Status.ACTIVE,
            ),
            "regular": self._ensure_financial_contract(
                finance_service,
                StudentFinancialContract,
                student=students["2026002"],
                template=templates["fundamental"],
                academic_year=academic_year,
                name="Contrato DEMO - Regular",
                start_competency=start_competency,
                target_status=StudentFinancialContract.Status.ACTIVE,
            ),
            "amendment": self._ensure_financial_contract(
                finance_service,
                StudentFinancialContract,
                student=students["2026003"],
                template=templates["contraturno"],
                academic_year=academic_year,
                name="Contrato DEMO - Aditivo Futuro",
                start_competency=start_competency,
                target_status=StudentFinancialContract.Status.ACTIVE,
            ),
            "draft": self._ensure_financial_contract(
                finance_service,
                StudentFinancialContract,
                student=students["2026005"],
                template=templates["infantil"],
                academic_year=academic_year,
                name="Contrato DEMO - Rascunho",
                start_competency=start_competency,
                target_status=StudentFinancialContract.Status.DRAFT,
            ),
            "suspended": self._ensure_financial_contract(
                finance_service,
                StudentFinancialContract,
                student=students["2026006"],
                template=templates["fundamental"],
                academic_year=academic_year,
                name="Contrato DEMO - Suspenso",
                start_competency=start_competency,
                target_status=StudentFinancialContract.Status.SUSPENDED,
            ),
            "cancelled": self._ensure_financial_contract(
                finance_service,
                StudentFinancialContract,
                student=students["2026007"],
                template=templates["contraturno"],
                academic_year=academic_year,
                name="Contrato DEMO - Cancelado",
                start_competency=start_competency,
                target_status=StudentFinancialContract.Status.CANCELLED,
            ),
        }
        if contracts["amendment"] is not None:
            self._ensure_future_amendment(
                finance_service,
                FinancialContractAmendment,
                contracts["amendment"],
                effective_competency=self._add_months(month_start, 2),
            )
        self._ensure_ad_hoc_billing(
            finance_service,
            BillingEntry,
            student=students["2026004"],
            due_date=today.replace(day=min(today.day, 28)),
        )
        if contracts["movements"] is not None:
            self._ensure_payment_scenarios(
                payment_service,
                BillingEntry,
                PaymentRecord,
                contracts["movements"],
                academic_year,
            )
        self._ensure_disabled_reminder_policy(
            finance_service,
            CollectionReminderPolicy,
        )
        return {
            "templates": FinancialPlanTemplate.objects.filter(academic_year=academic_year).count(),
            "contracts": StudentFinancialContract.objects.filter(
                academic_year=academic_year
            ).count(),
            "billings": BillingEntry.objects.count(),
            "payments": PaymentRecord.objects.count(),
        }

    def _ensure_financial_template(self, service, model, academic_year: int, **data):
        template = model.objects.filter(name=data["name"], academic_year=academic_year).first()
        if template is not None:
            return template
        try:
            return service.create_financial_template(
                {
                    "academic_year": academic_year,
                    "billing_frequency": "MONTHLY",
                    **data,
                }
            )
        except IntegrityError:
            return model.objects.get(name=data["name"], academic_year=academic_year)

    def _ensure_financial_contract(
        self,
        service,
        model,
        *,
        student,
        template,
        academic_year: int,
        name: str,
        start_competency: date,
        target_status: str,
    ):
        contract = model.objects.filter(name=name, academic_year=academic_year).first()
        if contract is not None and contract.student_id != student.pk:
            self._log("demo_finance_contract_skipped", scenario=name)
            return None
        if contract is None:
            if model.objects.filter(student=student, academic_year=academic_year).exists():
                self._log("demo_finance_contract_skipped", scenario=name)
                return None
            try:
                contract = service.create_contract(
                    {
                        "template_id": template.pk,
                        "student_id": student.pk,
                        "class_obj_id": self._active_class_id(student, academic_year),
                        "academic_year": academic_year,
                        "name": name,
                        "start_competency": start_competency,
                    }
                )
            except IntegrityError:
                contract = model.objects.filter(name=name, academic_year=academic_year).first()
                if contract is None:
                    self._log("demo_finance_contract_skipped", scenario=name)
                    return None
        if target_status == model.Status.DRAFT or contract.status == target_status:
            return contract
        if contract.status == model.Status.DRAFT:
            contract = service.activate_contract(contract.pk)
        if target_status == model.Status.SUSPENDED and contract.status == model.Status.ACTIVE:
            return service.suspend_contract(contract.pk, "Cenário DEMO temporariamente suspenso.")
        if target_status == model.Status.CANCELLED and contract.status == model.Status.ACTIVE:
            return service.cancel_contract(contract.pk, "Cenário DEMO cancelado antes da vigência.")
        return contract

    def _ensure_future_amendment(self, service, model, contract, *, effective_competency: date):
        amendment = model.objects.filter(contract=contract).first()
        if amendment is not None:
            return amendment
        try:
            return service.create_amendment(
                contract.pk,
                {
                    "effective_competency": effective_competency,
                    "installment_value": Decimal("460.00"),
                    "reason": "Atualização demonstrativa para o próximo período.",
                },
            )
        except IntegrityError:
            return model.objects.filter(contract=contract).first()

    def _ensure_ad_hoc_billing(self, service, model, *, student, due_date: date):
        description = "Taxa DEMO - Material complementar"
        competency = due_date.replace(day=1)
        billing = model.objects.filter(
            student=student,
            description=description,
            competency=competency,
        ).first()
        if billing is not None:
            return billing
        return service.create_ad_hoc_billing(
            {
                "student_id": student.pk,
                "description": description,
                "category": model.Category.MATERIAL,
                "amount": Decimal("185.00"),
                "due_date": due_date,
                "notes": "Lançamento avulso demonstrativo.",
            }
        )

    def _ensure_payment_scenarios(self, service, billing_model, payment_model, contract, year: int):
        billings = list(
            billing_model.objects.filter(
                contract=contract,
                schedule_revision=1,
                status=billing_model.Status.ACTIVE,
            ).order_by("installment_number")[:3]
        )
        if len(billings) != 3:
            return
        scenarios = (
            ("confirmed", billings[0], payment_model.Status.CONFIRMED),
            ("pending", billings[1], payment_model.Status.PENDING),
            ("reversed", billings[2], payment_model.Status.REVERSED),
        )
        for name, billing, target_status in scenarios:
            key = uuid5(NAMESPACE_URL, f"{self._PAYMENT_NAMESPACE}/{year}/{name}")
            paid_date = min(billing.due_date, timezone.localdate())
            payment = service.create_payment(
                allocations=[{"billing_id": billing.pk, "amount": billing.contractual_value}],
                paid_date=paid_date,
                payment_method=payment_model.PaymentMethod.PIX,
                reference=f"DEMO-{name.upper()}-{year}",
                idempotency_key=key,
            )
            if target_status == payment_model.Status.CONFIRMED:
                if payment.status == payment_model.Status.PENDING:
                    service.confirm_payment(payment.pk)
                continue
            if target_status == payment_model.Status.REVERSED:
                if payment.status == payment_model.Status.PENDING:
                    payment = service.confirm_payment(payment.pk)
                if payment.status == payment_model.Status.CONFIRMED:
                    service.reverse_payment(
                        payment.pk,
                        reason="Estorno demonstrativo de baixa duplicada.",
                    )

    def _ensure_disabled_reminder_policy(self, service, model):
        policy = model.objects.filter(name="Régua DEMO desabilitada").first()
        if policy is not None:
            return policy
        if model.objects.exists():
            self._log(
                "demo_finance_reminder_policy_skipped",
                existing_policy_count=model.objects.count(),
            )
            return None
        return service.configure_reminder_policy(
            {
                "name": "Régua DEMO desabilitada",
                "enabled": False,
                "offset_days": [-5, 0, 5],
                "channels": ["IN_APP"],
            }
        )

    @staticmethod
    def _active_class_id(student, academic_year: int):
        """Retorna a turma da matrícula ativa do aluno no ano do cenário."""
        from classes.contracts import Enrollment

        active_enrollments = Enrollment.objects.filter(
            student=student,
            status=Enrollment.Status.ACTIVE,
        ).order_by("-enrollment_date")
        return (
            active_enrollments.filter(class_obj__academic_year=academic_year)
            .values_list("class_obj_id", flat=True)
            .first()
            or active_enrollments.values_list("class_obj_id", flat=True).first()
        )

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        absolute = value.year * 12 + value.month - 1 + months
        return date(absolute // 12, absolute % 12 + 1, 1)
