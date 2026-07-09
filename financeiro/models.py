"""Modelos do modulo de Financeiro Escolar.

Encadeamento: FinancialPlan -> BillingEntry -> PaymentRecord.
- FinancialPlan: plano de cobranca por aluno/turma para um ano letivo.
- BillingEntry: cada parcela/mensalidade gerada a partir de um plano.
- PaymentRecord: baixa de pagamento (parcial ou total) sobre uma cobranca.
"""

from django.conf import settings
from django.db import models

from base.models import BaseModel


class FinancialPlan(BaseModel):
    """Plano financeiro de um aluno para um ano letivo.

    Agrupa a configuracao de mensalidades, descontos e politicas de multa/juros
    que geram cobrancas (BillingEntry) ao longo do ano.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        ACTIVE = "ACTIVE", "Ativo"
        SUSPENDED = "SUSPENDED", "Suspenso"
        CLOSED = "CLOSED", "Encerrado"

    class BillingFrequency(models.TextChoices):
        MONTHLY = "MONTHLY", "Mensal"
        BIMONTHLY = "BIMONTHLY", "Bimestral"
        QUARTERLY = "QUARTERLY", "Trimestral"
        ANNUAL = "ANNUAL", "Anual"

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,  # CASCADE: sem aluno, o plano financeiro perde sentido.
        related_name="financial_plans",
        verbose_name="Aluno",
    )
    class_obj = models.ForeignKey(
        "classes.Class",
        null=True,
        blank=True,
        on_delete=models.CASCADE,  # CASCADE: plano de turma acompanha a turma removida.
        related_name="financial_plans",
        verbose_name="Turma",
    )
    academic_year = models.PositiveIntegerField(verbose_name="Ano Letivo")
    name = models.CharField(max_length=200, verbose_name="Nome do Plano")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Situacao",
    )
    billing_frequency = models.CharField(
        max_length=20,
        choices=BillingFrequency.choices,
        default=BillingFrequency.MONTHLY,
        verbose_name="Frequencia de Cobranca",
    )
    installment_count = models.PositiveIntegerField(verbose_name="Numero de Parcelas")
    installment_value = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Valor da Parcela"
    )
    due_day = models.PositiveSmallIntegerField(
        verbose_name="Dia de Vencimento",
        help_text="Dia do mes para vencimento padrao das parcelas (1-28).",
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Valor de Desconto por Parcela",
    )
    late_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Multa por Atraso (%)",
    )
    daily_interest_percent = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=0,
        verbose_name="Juros Diarios (%)",
    )
    notes = models.TextField(blank=True, default="", verbose_name="Observacoes")

    class Meta:
        ordering = ["-academic_year", "name"]
        verbose_name = "Plano Financeiro"
        verbose_name_plural = "Planos Financeiros"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["academic_year"]),
            models.Index(fields=["class_obj", "academic_year"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                condition=models.Q(
                    is_active=True,
                    deleted_at__isnull=True,
                    status__in=["DRAFT", "ACTIVE"],
                ),
                name="uniq_active_financial_plan_per_student_year",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} — {self.student} ({self.academic_year})"


class BillingEntry(BaseModel):
    """Cobranca individual gerada a partir de um plano financeiro.

    Status: aberto, pago, vencido, cancelado. O estado 'pago' e derivado
    quando o total pago cobre o valor; 'vencido' e derivado da data de
    vencimento + ausencia de quitacao.
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberto"
        PAID = "PAID", "Pago"
        OVERDUE = "OVERDUE", "Vencido"
        CANCELLED = "CANCELLED", "Cancelado"

    plan = models.ForeignKey(
        FinancialPlan,
        on_delete=models.CASCADE,  # CASCADE: cobrança é derivada do plano.
        related_name="billings",
        verbose_name="Plano",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,  # CASCADE: cobrança não existe sem aluno.
        related_name="billings",
        verbose_name="Aluno",
    )
    installment_number = models.PositiveSmallIntegerField(verbose_name="Parcela")
    description = models.CharField(max_length=200, verbose_name="Descricao")
    original_value = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Valor Original"
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Desconto Aplicado",
    )
    paid_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Valor Pago",
    )
    due_date = models.DateField(verbose_name="Vencimento")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        verbose_name="Situacao",
    )
    cancelled_reason = models.TextField(
        blank=True, default="", verbose_name="Motivo de Cancelamento"
    )
    renegotiated_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="renegotiated_to",
        verbose_name="Originada por Renegociacao",
    )
    notes = models.TextField(blank=True, default="", verbose_name="Observacoes")

    class Meta:
        ordering = ["due_date", "installment_number"]
        verbose_name = "Cobranca"
        verbose_name_plural = "Cobrancas"
        unique_together = [("plan", "installment_number")]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["student", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.description} — {self.student} ({self.get_status_display()})"

    @property
    def outstanding_value(self):
        """Saldo devedor apos desconto e pagamentos."""
        return max(self.net_value - self.paid_value, 0)

    @property
    def net_value(self):
        """Valor liquido apos desconto."""
        return self.original_value - self.discount_value

    @property
    def is_settled(self) -> bool:
        """Indica se a cobranca esta quitada (saldo devedor zero)."""
        return self.outstanding_value == 0

    def computed_status(self, *, reference_date=None):
        """Deriva o status a partir dos pagamentos e da data de vencimento.

        Mantido como funcao pura para uso no service sem acoplar save.
        """
        from datetime import date

        reference = reference_date or date.today()
        if self.status == BillingEntry.Status.CANCELLED:
            return BillingEntry.Status.CANCELLED
        if self.is_settled:
            return BillingEntry.Status.PAID
        return (
            BillingEntry.Status.OVERDUE if self.due_date < reference else BillingEntry.Status.OPEN
        )


class PaymentRecord(BaseModel):
    """Registro de pagamento efetuado sobre uma cobranca (baixa)."""

    class ReconciliationStatus(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        CONFIRMED = "CONFIRMED", "Conciliado"
        REJECTED = "REJECTED", "Estornado"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Dinheiro"
        PIX = "PIX", "PIX"
        BANK_TRANSFER = "BANK_TRANSFER", "Transferencia Bancaria"
        CHECK = "CHECK", "Cheque"
        CARD = "CARD", "Cartao"
        OTHER = "OTHER", "Outro"

    billing = models.ForeignKey(
        BillingEntry,
        on_delete=models.CASCADE,  # CASCADE: pagamento acompanha sua cobrança.
        related_name="payments",
        verbose_name="Cobranca",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Pago")
    paid_date = models.DateField(verbose_name="Data de Pagamento")
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name="Forma de Pagamento",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_payments",
        verbose_name="Recebido por",
    )
    reconciliation_status = models.CharField(
        max_length=20,
        choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.PENDING,
        verbose_name="Situacao da Conciliacao",
    )
    reconciled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Conciliado em",
    )
    notes = models.TextField(blank=True, default="", verbose_name="Observacoes")

    class Meta:
        ordering = ["-paid_date"]
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"
        indexes = [
            models.Index(fields=["paid_date"]),
            models.Index(fields=["reconciliation_status"]),
            models.Index(fields=["billing", "paid_date"]),
        ]

    def __str__(self) -> str:
        return f"PaymentRecord({self.billing_id}, {self.amount})"
