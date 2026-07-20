"""Entidades centrais de contratos, cobranças e pagamentos financeiros."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import models

from base.models import BaseModel

ZERO = Decimal("0.00")


class StudentFinancialContract(BaseModel):
    """Contrato financeiro individual de um aluno para um ano letivo."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        ACTIVE = "ACTIVE", "Ativo"
        SUSPENDED = "SUSPENDED", "Suspenso"
        CLOSED = "CLOSED", "Encerrado"
        CANCELLED = "CANCELLED", "Cancelado"

    class BillingFrequency(models.TextChoices):
        MONTHLY = "MONTHLY", "Mensal"
        BIMONTHLY = "BIMONTHLY", "Bimestral"
        QUARTERLY = "QUARTERLY", "Trimestral"
        ANNUAL = "ANNUAL", "Anual"

    template = models.ForeignKey(
        "financeiro.FinancialPlanTemplate",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contracts",
        verbose_name="Modelo de Plano",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,  # Sem aluno, o contrato perde o objeto de cobrança.
        related_name="financial_contracts",
        verbose_name="Aluno",
    )
    class_obj = models.ForeignKey(
        "classes.Class",
        null=True,
        blank=True,
        on_delete=models.CASCADE,  # A referência escolar acompanha a turma do contrato.
        related_name="financial_contracts",
        verbose_name="Turma",
    )
    academic_year = models.PositiveIntegerField(verbose_name="Ano Letivo")
    name = models.CharField(max_length=200, verbose_name="Nome do Contrato")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Situação",
    )
    billing_frequency = models.CharField(
        max_length=20,
        choices=BillingFrequency.choices,
        default=BillingFrequency.MONTHLY,
        verbose_name="Frequência de Cobrança",
    )
    installment_count = models.PositiveIntegerField(verbose_name="Número de Parcelas")
    installment_value = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Valor da Parcela"
    )
    due_day = models.PositiveSmallIntegerField(
        verbose_name="Dia de Vencimento",
        help_text="Dia do mês para vencimento das parcelas (1-28).",
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=ZERO,
        verbose_name="Desconto por Parcela",
    )
    late_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=ZERO,
        verbose_name="Multa por Atraso (%)",
    )
    daily_interest_percent = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=ZERO,
        verbose_name="Juros Diários (%)",
    )
    start_competency = models.DateField(null=True, blank=True, verbose_name="Competência Inicial")
    end_competency = models.DateField(null=True, blank=True, verbose_name="Competência Final")
    terms_revision = models.PositiveIntegerField(default=1, verbose_name="Revisão dos Termos")
    notes = models.TextField(blank=True, default="", verbose_name="Observações")

    class Meta:
        ordering = ["-academic_year", "name"]
        verbose_name = "Contrato Financeiro"
        verbose_name_plural = "Contratos Financeiros"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["academic_year"]),
            models.Index(fields=["class_obj", "academic_year"]),
            models.Index(fields=["student", "academic_year"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                condition=models.Q(
                    is_active=True,
                    deleted_at__isnull=True,
                    status__in=["DRAFT", "ACTIVE", "SUSPENDED"],
                ),
                name="uniq_current_financial_contract_student_year",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.student} ({self.academic_year})"


class BillingEntry(BaseModel):
    """Título a receber originado de contrato ou lançamento avulso."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Ativa"
        CANCELLED = "CANCELLED", "Cancelada"

    class Category(models.TextChoices):
        TUITION = "TUITION", "Mensalidade"
        FEE = "FEE", "Taxa"
        MATERIAL = "MATERIAL", "Material"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste"

    contract = models.ForeignKey(
        StudentFinancialContract,
        null=True,
        blank=True,
        on_delete=models.CASCADE,  # Títulos contratuais acompanham seu contrato.
        related_name="billings",
        verbose_name="Contrato",
    )
    amendment = models.ForeignKey(
        "financeiro.FinancialContractAmendment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_billings",
        verbose_name="Aditivo",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,  # O título não existe sem seu devedor escolar.
        related_name="billings",
        verbose_name="Aluno",
    )
    installment_number = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="Parcela"
    )
    schedule_revision = models.PositiveIntegerField(default=1, verbose_name="Revisão da Agenda")
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.TUITION,
        verbose_name="Categoria",
    )
    description = models.CharField(max_length=200, verbose_name="Descrição")
    principal_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Principal")
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, verbose_name="Desconto"
    )
    late_fee_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, verbose_name="Multa"
    )
    interest_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, verbose_name="Juros"
    )
    paid_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, verbose_name="Total Pago"
    )
    paid_principal_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, verbose_name="Principal Pago"
    )
    paid_late_fee_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, verbose_name="Multa Paga"
    )
    paid_interest_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, verbose_name="Juros Pagos"
    )
    competency = models.DateField(null=True, blank=True, verbose_name="Competência")
    due_date = models.DateField(verbose_name="Vencimento")
    interest_calculated_until = models.DateField(
        null=True, blank=True, verbose_name="Juros Calculados Até"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Situação",
    )
    cancelled_reason = models.TextField(blank=True, default="", verbose_name="Motivo")
    renegotiated_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="renegotiated_to",
        verbose_name="Originada por Renegociação",
    )
    notes = models.TextField(blank=True, default="", verbose_name="Observações Internas")

    class Meta:
        ordering = ["due_date", "installment_number"]
        verbose_name = "Cobrança"
        verbose_name_plural = "Cobranças"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["competency"]),
            models.Index(fields=["student", "status"]),
            models.Index(fields=["contract", "installment_number"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "installment_number", "schedule_revision"],
                condition=models.Q(contract__isnull=False),
                name="uniq_contract_installment_revision",
            )
        ]

    def __str__(self) -> str:
        return f"{self.description} - {self.student}"

    @property
    def contractual_value(self) -> Decimal:
        """Valor principal líquido do desconto contratual."""
        return max((self.principal_value or ZERO) - (self.discount_value or ZERO), ZERO)

    @property
    def net_value(self) -> Decimal:
        """Total devido já acrescido dos encargos efetivamente apurados."""
        return (
            self.contractual_value + (self.late_fee_value or ZERO) + (self.interest_value or ZERO)
        )

    @property
    def outstanding_value(self) -> Decimal:
        """Saldo total após pagamentos confirmados."""
        return max(self.net_value - (self.paid_value or ZERO), ZERO)

    @property
    def is_settled(self) -> bool:
        return self.outstanding_value == ZERO

    @property
    def settlement_status(self) -> str:
        if self.is_settled:
            return "PAID"
        if (self.paid_value or ZERO) > ZERO:
            return "PARTIAL"
        return "UNPAID"

    @property
    def settlement_status_label(self) -> str:
        return {
            "PAID": "Paga",
            "PARTIAL": "Parcial",
            "UNPAID": "Não paga",
        }[self.settlement_status]

    def due_status(self, *, reference_date: date | None = None) -> str:
        reference = reference_date or date.today()
        if self.is_settled or self.status == self.Status.CANCELLED:
            return "CLOSED"
        if self.due_date < reference:
            return "OVERDUE"
        if self.due_date == reference:
            return "DUE"
        return "UPCOMING"

    @property
    def due_status_label(self) -> str:
        return {
            "CLOSED": "Encerrada",
            "OVERDUE": "Vencida",
            "DUE": "Vence hoje",
            "UPCOMING": "A vencer",
        }[self.due_status()]


from financeiro.receivables_models import (  # noqa: E402,F401
    CollectionReminder,
    CollectionReminderPolicy,
    FinancialContractAmendment,
    FinancialPlanTemplate,
    FinancialSequence,
    PaymentAllocation,
    PaymentRecord,
)

__all__ = [
    "BillingEntry",
    "CollectionReminder",
    "CollectionReminderPolicy",
    "FinancialContractAmendment",
    "FinancialPlanTemplate",
    "FinancialSequence",
    "PaymentAllocation",
    "PaymentRecord",
    "StudentFinancialContract",
]
