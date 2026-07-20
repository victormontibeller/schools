"""Consultas tenant-scoped do contas a receber financeiro."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Q

from base.exceptions import ObjectNotFoundError
from base.selectors import BaseSelector, PageResult
from financeiro.report_selectors import BillingReportingMixin

ZERO = Decimal("0.00")
MONEY = DecimalField(max_digits=12, decimal_places=2)


def _billing_balance_expression():
    return ExpressionWrapper(
        F("principal_value")
        - F("discount_value")
        + F("late_fee_value")
        + F("interest_value")
        - F("paid_value"),
        output_field=MONEY,
    )


class FinanceScopeMixin:
    """Aplica o escopo de guarda quando o ator é Responsável."""

    def __init__(self, user=None):
        self.user = user

    def _scope_students(self, queryset, *, prefix: str = "student"):
        if not self.user:
            return queryset
        from core.access_catalog import GUARDIAN
        from core.permissions import role_name

        if role_name(self.user) != GUARDIAN:
            return queryset
        filters = {
            f"{prefix}__guardians__guardian__user_id": self.user.pk,
            f"{prefix}__guardians__guardian__is_active": True,
            f"{prefix}__guardians__has_custody": True,
        }
        return queryset.filter(**filters).distinct()

    def _is_guardian(self) -> bool:
        from core.access_catalog import GUARDIAN
        from core.permissions import role_name

        return bool(self.user and role_name(self.user) == GUARDIAN)


class FinancialTemplateSelector(BaseSelector):
    """Leituras dos modelos reutilizáveis de plano."""

    @property
    def model_class(self):
        from financeiro.models import FinancialPlanTemplate

        return FinancialPlanTemplate

    def list_templates(
        self, *, search="", year=None, order_by="-academic_year", page=1, page_size=20
    ) -> PageResult:
        qs = self.model_class.objects.all()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        if year:
            qs = qs.filter(academic_year=year)
        return self._paginate(qs.order_by(order_by, "name"), page=page, page_size=page_size)

    def get_template(self, template_id):
        try:
            return self.model_class.objects.get(pk=template_id)
        except self.model_class.DoesNotExist:
            raise ObjectNotFoundError("FinancialPlanTemplate", str(template_id)) from None


class FinancialContractSelector(FinanceScopeMixin, BaseSelector):
    """Leituras de contratos financeiros individuais."""

    @property
    def model_class(self):
        from financeiro.models import StudentFinancialContract

        return StudentFinancialContract

    def list_contracts(
        self,
        search: str = "",
        status: str = "",
        order_by: str = "name",
        page: int = 1,
        page_size: int = 20,
    ) -> PageResult:
        qs = self.model_class.objects.select_related("student", "class_obj", "template")
        qs = self._scope_students(qs)
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(student__enrollment_number__icontains=search)
            )
        return self._paginate(qs.order_by(order_by), page=page, page_size=page_size)

    def get_contract(self, contract_id):
        qs = self._scope_students(
            self.model_class.objects.select_related("student", "class_obj", "template")
        )
        try:
            return qs.get(pk=contract_id)
        except self.model_class.DoesNotExist:
            raise ObjectNotFoundError("StudentFinancialContract", str(contract_id)) from None


class BillingSelector(BillingReportingMixin, FinanceScopeMixin, BaseSelector):
    """Cobranças, extratos, inadimplência e indicadores."""

    @property
    def model_class(self):
        from financeiro.models import BillingEntry

        return BillingEntry

    def base_queryset(self):
        qs = self.model_class.objects.select_related("student", "contract", "amendment").annotate(
            balance=_billing_balance_expression()
        )
        return self._scope_students(qs)

    def list_billings(
        self,
        search: str = "",
        status: str = "",
        page: int = 1,
        page_size: int = 20,
        class_id=None,
        contract_id=None,
        date_from=None,
        date_to=None,
        order_by="-due_date",
    ) -> PageResult:
        from financeiro.models import BillingEntry

        qs = self.base_queryset()
        if search:
            qs = qs.filter(
                Q(description__icontains=search)
                | Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(student__enrollment_number__icontains=search)
            )
        if class_id:
            qs = qs.filter(contract__class_obj_id=class_id)
        if contract_id:
            qs = qs.filter(contract_id=contract_id)
        if date_from:
            qs = qs.filter(due_date__gte=date_from)
        if date_to:
            qs = qs.filter(due_date__lte=date_to)
        today = dt.date.today()
        if status == "CANCELLED":
            qs = qs.filter(status=BillingEntry.Status.CANCELLED)
        elif status == "PAID":
            qs = qs.exclude(status=BillingEntry.Status.CANCELLED).filter(balance__lte=ZERO)
        elif status == "OVERDUE":
            qs = qs.exclude(status=BillingEntry.Status.CANCELLED).filter(
                balance__gt=ZERO, due_date__lt=today
            )
        elif status == "PARTIAL":
            qs = qs.exclude(status=BillingEntry.Status.CANCELLED).filter(
                paid_value__gt=ZERO, balance__gt=ZERO
            )
        elif status == "OPEN":
            qs = qs.exclude(status=BillingEntry.Status.CANCELLED).filter(
                balance__gt=ZERO, due_date__gte=today
            )
        return self._paginate(qs.order_by(order_by), page=page, page_size=page_size)

    def get_billing_by_id(self, billing_id):
        try:
            return self.base_queryset().get(pk=billing_id)
        except self.model_class.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None

    def get_payments(self, billing_id):
        from financeiro.models import PaymentRecord

        # Revalida o objeto antes de expor as transações relacionadas. Isso mantém
        # o mesmo escopo de guarda mesmo quando o selector é reutilizado fora da view.
        self.get_billing_by_id(billing_id)
        return (
            PaymentRecord.all_objects.filter(Q(allocations__billing_id=billing_id))
            .select_related("received_by", "confirmed_by", "reversed_by")
            .distinct()
            .order_by("-paid_date", "-created_at")
        )

    def get_billings_for_contract(self, contract_id):
        return (
            self.base_queryset()
            .filter(contract_id=contract_id)
            .order_by("due_date", "installment_number", "schedule_revision")
        )

    def student_statement(self, student_id):
        return self._scope_students(self.base_queryset().filter(student_id=student_id)).order_by(
            "competency", "due_date"
        )

    def open_for_student(self, student_id):
        from financeiro.models import BillingEntry

        return (
            self._scope_students(self.base_queryset().filter(student_id=student_id))
            .exclude(status=BillingEntry.Status.CANCELLED)
            .filter(balance__gt=ZERO)
            .order_by("due_date")
        )


class PaymentSelector(FinanceScopeMixin, BaseSelector):
    """Fila operacional de conciliações."""

    def list_payments(
        self, *, search="", status="PENDING", order_by="-paid_date", page=1, page_size=20
    ) -> PageResult:
        from financeiro.models import PaymentRecord

        qs = PaymentRecord.objects.prefetch_related("allocations__billing__student")
        qs = self._scope_students(qs, prefix="allocations__billing__student")
        if search:
            qs = qs.filter(Q(receipt_number__icontains=search) | Q(reference__icontains=search))
        if status:
            qs = qs.filter(status=status)
        return self._paginate(qs.order_by(order_by, "-created_at"), page=page, page_size=page_size)

    def get_payment(self, payment_id):
        from financeiro.models import PaymentRecord

        try:
            qs = PaymentRecord.all_objects.prefetch_related("allocations__billing__student")
            qs = self._scope_students(qs, prefix="allocations__billing__student")
            payment = qs.get(pk=payment_id)
            if self._is_guardian():
                allocation_count = payment.allocations.count()
                allowed_count = (
                    payment.allocations.filter(
                        billing__student__guardians__guardian__user_id=self.user.pk,
                        billing__student__guardians__guardian__is_active=True,
                        billing__student__guardians__has_custody=True,
                    )
                    .distinct()
                    .count()
                )
                if allowed_count != allocation_count:
                    raise PaymentRecord.DoesNotExist
            return payment
        except PaymentRecord.DoesNotExist:
            raise ObjectNotFoundError("PaymentRecord", str(payment_id)) from None


class ReminderSelector(BaseSelector):
    """Políticas e histórico de lembretes."""

    def get_policy(self):
        from financeiro.models import CollectionReminderPolicy

        return CollectionReminderPolicy.objects.order_by("created_at").first()

    def list_reminders(
        self, *, search="", status="", order_by="-scheduled_for", page=1, page_size=20
    ) -> PageResult:
        from financeiro.models import CollectionReminder

        qs = CollectionReminder.objects.select_related("billing", "guardian", "recipient")
        if search:
            qs = qs.filter(billing__description__icontains=search)
        if status:
            qs = qs.filter(status=status)
        return self._paginate(qs.order_by(order_by), page=page, page_size=page_size)
