"""Leituras agregadas de competência, caixa e inadimplência."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from itertools import islice

from django.db.models import Case, CharField, Count, DecimalField, F, Min, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from base.selectors import PageResult

ZERO = Decimal("0.00")
MONEY = DecimalField(max_digits=12, decimal_places=2)


class BillingReportingMixin:
    """Relatórios agregados; a fachada pública continua em ``BillingSelector``."""

    OVERDUE_BANDS = (
        ("1-30 dias", 1, 30),
        ("31-60 dias", 31, 60),
        ("60+ dias", 61, None),
    )

    def inadimplencia_por_faixa(self, *, reference_date=None) -> list[dict]:
        from financeiro.models import BillingEntry

        reference = reference_date or timezone.localdate()
        base = (
            self.base_queryset()
            .exclude(status=BillingEntry.Status.CANCELLED)
            .filter(balance__gt=ZERO, due_date__lt=reference)
        )
        result = []
        for label, minimum, maximum in self.OVERDUE_BANDS:
            filters = {"due_date__lte": reference - dt.timedelta(days=minimum)}
            if maximum is not None:
                filters["due_date__gte"] = reference - dt.timedelta(days=maximum)
            aggregate = base.filter(**filters).aggregate(
                quantity=Count("pk"),
                total=Coalesce(Sum("balance"), Value(ZERO), output_field=MONEY),
            )
            result.append(
                {
                    "faixa": label,
                    "quantidade": int(aggregate["quantity"]),
                    "total": aggregate["total"],
                }
            )
        return result

    def competence_report(self, *, year=None, month=None) -> dict:
        from financeiro.models import BillingEntry

        today = timezone.localdate()
        selected_year = year or today.year
        start = dt.date(selected_year, month or 1, 1)
        end = (
            dt.date(selected_year + 1, 1, 1)
            if not month or month == 12
            else dt.date(selected_year, month + 1, 1)
        )
        if not month:
            end = dt.date(selected_year + 1, 1, 1)
        qs = (
            self.base_queryset()
            .exclude(status=BillingEntry.Status.CANCELLED)
            .filter(competency__gte=start, competency__lt=end)
        )
        totals = qs.aggregate(
            principal=Coalesce(Sum("principal_value"), Value(ZERO), output_field=MONEY),
            discounts=Coalesce(Sum("discount_value"), Value(ZERO), output_field=MONEY),
            charges=Coalesce(
                Sum(F("late_fee_value") + F("interest_value")),
                Value(ZERO),
                output_field=MONEY,
            ),
            received=Coalesce(Sum("paid_value"), Value(ZERO), output_field=MONEY),
            outstanding=Coalesce(Sum("balance"), Value(ZERO), output_field=MONEY),
        )
        from financeiro.models import PaymentAllocation, PaymentRecord

        # Recebimentos pertencem à competência original mesmo após renegociação.
        totals["received"] = PaymentAllocation.objects.filter(
            billing_id__in=self.base_queryset().values("pk"),
            billing__competency__gte=start,
            billing__competency__lt=end,
            payment__status=PaymentRecord.Status.CONFIRMED,
            payment__deleted_at__isnull=True,
        ).aggregate(total=Coalesce(Sum("amount"), Value(ZERO), output_field=MONEY))["total"]
        totals["expected"] = totals["principal"] - totals["discounts"]
        totals["period"] = f"{month:02d}/{selected_year}" if month else str(selected_year)
        return totals

    def _overdue_queryset(self, *, reference_date=None):
        """Drill-down agrupado no banco por faixa, aluno, turma e contrato."""
        from financeiro.models import BillingEntry

        reference = reference_date or timezone.localdate()
        qs = (
            self.base_queryset()
            .exclude(status=BillingEntry.Status.CANCELLED)
            .filter(balance__gt=ZERO, due_date__lt=reference)
            .annotate(
                aging_band=Case(
                    When(
                        due_date__gte=reference - dt.timedelta(days=30),
                        then=Value("1-30 dias"),
                    ),
                    When(
                        due_date__gte=reference - dt.timedelta(days=60),
                        then=Value("31-60 dias"),
                    ),
                    default=Value("60+ dias"),
                    output_field=CharField(),
                )
            )
            .values(
                "aging_band",
                "student_id",
                "student__first_name",
                "student__last_name",
                "contract_id",
                "contract__name",
                "contract__class_obj__name",
            )
            .annotate(
                quantity=Count("pk"),
                oldest_due=Min("due_date"),
                total=Sum("balance"),
            )
            .order_by(
                "aging_band",
                "student__first_name",
                "student__last_name",
                "student_id",
                "contract_id",
            )
        )
        return qs

    def overdue_details(self, *, reference_date=None, page=1, page_size=20) -> PageResult:
        """Pagina o relatório usando o limite canônico de até cem grupos."""
        return self._paginate(
            self._overdue_queryset(reference_date=reference_date), page=page, page_size=page_size
        )

    def iter_overdue_details(self, *, tenant_schema: str, reference_date=None) -> Iterator[dict]:
        """Lê blocos limitados mantendo o tenant explícito durante cada avanço."""
        from base.context import tenant_schema_context

        with tenant_schema_context(tenant_schema):
            rows_iterator = self._overdue_queryset(reference_date=reference_date).iterator(
                chunk_size=500
            )
        try:
            while True:
                with tenant_schema_context(tenant_schema):
                    rows = list(islice(rows_iterator, 500))
                if not rows:
                    return
                yield from rows
        finally:
            with tenant_schema_context(tenant_schema):
                rows_iterator.close()

    def cash_report(self, *, year=None, month=None) -> dict:
        from financeiro.models import PaymentRecord

        today = timezone.localdate()
        selected_year = year or today.year
        start = dt.date(selected_year, month or 1, 1)
        end = (
            dt.date(selected_year + 1, 1, 1)
            if not month or month == 12
            else dt.date(selected_year, month + 1, 1)
        )
        confirmed = PaymentRecord.objects.filter(
            status__in=(
                PaymentRecord.Status.CONFIRMED,
                PaymentRecord.Status.REVERSED,
            ),
            reconciled_at__isnull=False,
            paid_date__gte=start,
            paid_date__lt=end,
        ).aggregate(total=Coalesce(Sum("amount"), Value(ZERO), output_field=MONEY))["total"]
        reversals = PaymentRecord.objects.filter(
            status=PaymentRecord.Status.REVERSED,
            reversed_at__date__gte=start,
            reversed_at__date__lt=end,
        ).aggregate(total=Coalesce(Sum("amount"), Value(ZERO), output_field=MONEY))["total"]
        return {
            "period": f"{month:02d}/{selected_year}" if month else str(selected_year),
            "inflow": confirmed,
            "reversals": reversals,
            "net": confirmed - reversals,
        }

    def finance_kpis(self, *, reference_date=None) -> dict:
        from financeiro.models import BillingEntry, CollectionReminder, PaymentRecord

        reference = reference_date or timezone.localdate()
        qs = (
            self.base_queryset()
            .exclude(status=BillingEntry.Status.CANCELLED)
            .filter(balance__gt=ZERO)
        )
        due = qs.filter(due_date__gte=reference).aggregate(
            total=Coalesce(Sum("balance"), Value(ZERO), output_field=MONEY)
        )["total"]
        overdue = qs.filter(due_date__lt=reference).aggregate(
            total=Coalesce(Sum("balance"), Value(ZERO), output_field=MONEY)
        )["total"]
        cash = (
            ZERO
            if self._is_guardian()
            else self.cash_report(year=reference.year, month=reference.month)["net"]
        )
        return {
            "total_aberto": due,
            "total_vencido": overdue,
            "recebido_mes": cash,
            "partial_count": qs.filter(paid_value__gt=ZERO).count(),
            "pending_reconciliation": (
                0 if self._is_guardian() else PaymentRecord.objects.filter(status="PENDING").count()
            ),
            "reminder_failures": (
                0
                if self._is_guardian()
                else CollectionReminder.objects.filter(status="FAILED").count()
            ),
        }
