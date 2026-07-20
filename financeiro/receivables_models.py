"""Modelos auxiliares do contas a receber financeiro."""

import uuid

from django.conf import settings
from django.db import models

from base.models import BaseModel


class FinancialPlanTemplate(BaseModel):
    """Modelo reutilizável cujos termos são copiados para novos contratos."""

    name = models.CharField(max_length=200, verbose_name="Nome")
    academic_year = models.PositiveIntegerField(verbose_name="Ano Letivo")
    billing_frequency = models.CharField(
        max_length=20,
        choices=(
            ("MONTHLY", "Mensal"),
            ("BIMONTHLY", "Bimestral"),
            ("QUARTERLY", "Trimestral"),
            ("ANNUAL", "Anual"),
        ),
        default="MONTHLY",
        verbose_name="Frequência",
    )
    installment_count = models.PositiveIntegerField(verbose_name="Parcelas")
    installment_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor")
    due_day = models.PositiveSmallIntegerField(verbose_name="Dia de Vencimento")
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Desconto Padrão"
    )
    late_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name="Multa (%)"
    )
    daily_interest_percent = models.DecimalField(
        max_digits=6, decimal_places=4, default=0, verbose_name="Juros Diários (%)"
    )
    description = models.TextField(blank=True, default="", verbose_name="Descrição")

    class Meta:
        ordering = ["-academic_year", "name"]
        verbose_name = "Modelo de Plano Financeiro"
        verbose_name_plural = "Modelos de Planos Financeiros"
        indexes = [models.Index(fields=["academic_year", "name"])]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "academic_year"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="uniq_active_financial_template_year",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.academic_year})"


class FinancialContractAmendment(BaseModel):
    """Revisão futura dos termos de um contrato ativo."""

    contract = models.ForeignKey(
        "financeiro.StudentFinancialContract",
        on_delete=models.CASCADE,
        related_name="amendments",
        verbose_name="Contrato",
    )
    revision = models.PositiveIntegerField(verbose_name="Revisão")
    effective_competency = models.DateField(verbose_name="Vigência")
    changed_terms = models.JSONField(default=dict, verbose_name="Termos Alterados")
    reason = models.TextField(verbose_name="Motivo")

    class Meta:
        ordering = ["-revision"]
        verbose_name = "Aditivo Financeiro"
        verbose_name_plural = "Aditivos Financeiros"
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "revision"], name="uniq_contract_amendment_revision"
            )
        ]
        indexes = [models.Index(fields=["contract", "effective_competency"])]

    def __str__(self) -> str:
        return f"Amendment({self.contract_id}, {self.revision})"


class PaymentRecord(BaseModel):
    """Transação manual que pode ser distribuída entre várias cobranças."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        CONFIRMED = "CONFIRMED", "Conciliado"
        REVERSED = "REVERSED", "Estornado"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Dinheiro"
        PIX = "PIX", "PIX"
        BANK_TRANSFER = "BANK_TRANSFER", "Transferência Bancária"
        CHECK = "CHECK", "Cheque"
        CARD = "CARD", "Cartão"
        OTHER = "OTHER", "Outro"

    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor")
    paid_date = models.DateField(verbose_name="Data do Pagamento")
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name="Forma de Pagamento",
    )
    reference = models.CharField(max_length=120, blank=True, default="", verbose_name="Referência")
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_payments",
        verbose_name="Registrado por",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Conciliação",
    )
    reconciled_at = models.DateTimeField(null=True, blank=True, verbose_name="Conciliado em")
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_payments",
        verbose_name="Conciliado por",
    )
    reversed_at = models.DateTimeField(null=True, blank=True, verbose_name="Estornado em")
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reversed_payments",
        verbose_name="Estornado por",
    )
    reversal_reason = models.TextField(blank=True, default="", verbose_name="Motivo do Estorno")
    receipt_number = models.CharField(max_length=24, blank=True, default="", verbose_name="Recibo")
    notes = models.TextField(blank=True, default="", verbose_name="Observações Internas")

    class Meta:
        ordering = ["-paid_date", "-created_at"]
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"
        indexes = [
            models.Index(fields=["paid_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["receipt_number"]),
        ]

    def __str__(self) -> str:
        return f"PaymentRecord({self.pk}, {self.amount})"


class PaymentAllocation(BaseModel):
    """Parcela auditável de um pagamento destinada a uma cobrança."""

    payment = models.ForeignKey(
        "financeiro.PaymentRecord",
        on_delete=models.CASCADE,
        related_name="allocations",
        verbose_name="Pagamento",
    )
    billing = models.ForeignKey(
        "financeiro.BillingEntry",
        on_delete=models.CASCADE,
        related_name="payment_allocations",
        verbose_name="Cobrança",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Alocado")
    principal_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Principal"
    )
    late_fee_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Multa"
    )
    interest_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Juros"
    )

    class Meta:
        ordering = ["billing__due_date", "created_at"]
        verbose_name = "Alocação de Pagamento"
        verbose_name_plural = "Alocações de Pagamento"
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "billing"], name="uniq_payment_billing_allocation"
            )
        ]
        indexes = [models.Index(fields=["billing", "payment"])]

    def __str__(self) -> str:
        return f"PaymentAllocation({self.payment_id}, {self.billing_id})"


class FinancialSequence(BaseModel):
    """Sequência tenant-scoped protegida por lock pessimista."""

    kind = models.CharField(max_length=30, verbose_name="Tipo")
    year = models.PositiveIntegerField(verbose_name="Ano")
    last_value = models.PositiveIntegerField(default=0, verbose_name="Último Valor")

    class Meta:
        verbose_name = "Sequência Financeira"
        verbose_name_plural = "Sequências Financeiras"
        constraints = [
            models.UniqueConstraint(fields=["kind", "year"], name="uniq_financial_sequence_year")
        ]

    def __str__(self) -> str:
        return f"FinancialSequence({self.kind}, {self.year})"


class CollectionReminderPolicy(BaseModel):
    """Régua de cobrança configurada dentro do schema da escola."""

    name = models.CharField(max_length=120, default="Régua principal", verbose_name="Nome")
    enabled = models.BooleanField(default=False, verbose_name="Ativa")
    offset_days = models.JSONField(default=list, blank=True, verbose_name="Dias Relativos")
    channels = models.JSONField(default=list, blank=True, verbose_name="Canais")

    class Meta:
        ordering = ["name"]
        verbose_name = "Política de Lembretes"
        verbose_name_plural = "Políticas de Lembretes"

    def __str__(self) -> str:
        return self.name


class CollectionReminder(BaseModel):
    """Tentativa deduplicada de lembrete para um responsável com guarda."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        SENT = "SENT", "Enviado"
        SKIPPED = "SKIPPED", "Ignorado"
        FAILED = "FAILED", "Falhou"

    billing = models.ForeignKey(
        "financeiro.BillingEntry",
        on_delete=models.CASCADE,
        related_name="collection_reminders",
        verbose_name="Cobrança",
    )
    guardian = models.ForeignKey(
        "guardians.Guardian",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="collection_reminders",
        verbose_name="Responsável",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="collection_reminders",
        verbose_name="Destinatário",
    )
    channel = models.CharField(max_length=20, verbose_name="Canal")
    rule_offset_days = models.SmallIntegerField(verbose_name="Regra (dias)")
    scheduled_for = models.DateField(verbose_name="Data Programada")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="Situação"
    )
    message_log_id = models.UUIDField(null=True, blank=True, verbose_name="Log da Mensagem")
    error_code = models.CharField(max_length=80, blank=True, default="", verbose_name="Código")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Enviado em")

    class Meta:
        ordering = ["-scheduled_for", "-created_at"]
        verbose_name = "Lembrete de Cobrança"
        verbose_name_plural = "Lembretes de Cobrança"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "billing",
                    "guardian",
                    "channel",
                    "rule_offset_days",
                    "scheduled_for",
                ],
                name="uniq_collection_reminder_delivery",
            )
        ]
        indexes = [models.Index(fields=["status", "scheduled_for"])]

    def __str__(self) -> str:
        return f"CollectionReminder({self.pk})"
