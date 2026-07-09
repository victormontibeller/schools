"""FinanceSelector: consultas somente-leitura para o modulo Financeiro.

Inclui listagem por status com busca, faixas de inadimplencia e relatorio
mensal de receita prevista x recebida.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db.models import Q, Sum

from base.exceptions import ObjectNotFoundError
from base.selectors import MAX_PAGE_SIZE, BaseSelector, PageResult


class FinancialPlanSelector(BaseSelector):
    """Consultas somente-leitura de planos financeiros."""

    @property
    def model_class(self):
        from financeiro.models import FinancialPlan

        return FinancialPlan

    def list_plans(
        self,
        search: str = "",
        status: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> PageResult:
        """Lista planos com busca por aluno/plano e filtro por status."""
        from financeiro.models import FinancialPlan

        qs = FinancialPlan.objects.all().select_related("student", "class_obj")
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(student__enrollment_number__icontains=search)
            )
        qs = qs.order_by("-academic_year", "name")
        return self._paginate(qs, page=page, page_size=page_size)

    def get_plan_by_id(self, plan_id):
        """Retorna o plano por id com relacionamentos ou lanca ObjectNotFoundError."""
        from financeiro.models import FinancialPlan

        try:
            return FinancialPlan.objects.select_related("student", "class_obj").get(pk=plan_id)
        except FinancialPlan.DoesNotExist:
            raise ObjectNotFoundError("FinancialPlan", str(plan_id)) from None

    def _paginate(self, qs, page: int = 1, page_size: int = 20) -> PageResult:
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        page = max(1, page)
        total = qs.count()
        offset = (page - 1) * page_size
        return PageResult(
            items=list(qs[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )


class BillingSelector(BaseSelector):
    """Consultas somente-leitura de cobrancas."""

    # Faixas de atraso em dias: (label, min_days, max_days)
    OVERDUE_BANDS = (
        ("1-30 dias", 1, 30),
        ("31-60 dias", 31, 60),
        ("60+ dias", 61, None),
    )

    @property
    def model_class(self):
        from financeiro.models import BillingEntry

        return BillingEntry

    def list_billings(
        self,
        search: str = "",
        status: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> PageResult:
        """Lista cobrancas com busca por aluno/descricao e filtro por status."""
        from financeiro.models import BillingEntry

        qs = BillingEntry.objects.all().select_related("student", "plan")
        if search:
            qs = qs.filter(
                Q(description__icontains=search)
                | Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(student__enrollment_number__icontains=search)
            )
        qs = qs.order_by("-due_date")
        if status in (
            BillingEntry.Status.OPEN,
            BillingEntry.Status.OVERDUE,
            BillingEntry.Status.PAID,
        ):
            items = self._billings_by_computed_status(qs, status)
            return self._paginate_items(items, page=page, page_size=page_size)
        if status:
            qs = qs.filter(status=status)
        return self._paginate(qs, page=page, page_size=page_size)

    def get_billing_by_id(self, billing_id):
        """Retorna a cobranca por id com plan, student e pagamentos ou lanca erro."""
        from financeiro.models import BillingEntry

        try:
            return BillingEntry.objects.select_related("student", "plan", "renegotiated_from").get(
                pk=billing_id
            )
        except BillingEntry.DoesNotExist:
            raise ObjectNotFoundError("BillingEntry", str(billing_id)) from None

    def get_payments(self, billing_id):
        """Retorna pagamentos de uma cobranca ordenados por data (mais novo primeiro)."""
        from financeiro.models import PaymentRecord

        return PaymentRecord.all_objects.filter(billing_id=billing_id).order_by("-paid_date")

    def get_billings_for_plan(self, plan_id):
        """Retorna todas as cobrancas de um plano, ordenadas por vencimento."""

        from financeiro.models import BillingEntry

        return BillingEntry.objects.filter(plan_id=plan_id).order_by(
            "due_date", "installment_number"
        )

    def inadimplencia_por_faixa(self, *, reference_date: dt.date | None = None) -> list[dict]:
        """Inadimplencia por faixa de atraso (1-30, 31-60, 60+).

        Returns:
            [{"faixa": str, "quantidade": int, "total": Decimal}, ...]
        """
        from financeiro.models import BillingEntry

        reference = reference_date or dt.date.today()
        base_items = self._billings_by_computed_status(
            BillingEntry.objects.exclude(status=BillingEntry.Status.CANCELLED),
            BillingEntry.Status.OVERDUE,
            reference_date=reference,
        )
        result = []
        for label, min_d, max_d in self.OVERDUE_BANDS:
            items = [
                billing
                for billing in base_items
                if billing.due_date <= reference - dt.timedelta(days=min_d)
                and (max_d is None or billing.due_date >= reference - dt.timedelta(days=max_d))
            ]
            total = sum((b.outstanding_value for b in items), Decimal("0.00"))
            result.append({"faixa": label, "quantidade": len(items), "total": total})
        return result

    def relatorio_previsto_x_recebido(
        self,
        *,
        year: int | None = None,
        month: int | None = None,
    ) -> dict:
        """Relatorio mensal de receita prevista x recebida.

        Se `month` for None, agrega o ano inteiro.
        """
        from financeiro.models import BillingEntry

        today = dt.date.today()
        y = year or today.year
        qs = BillingEntry.objects.exclude(status=BillingEntry.Status.CANCELLED)
        if month:
            start = dt.date(y, month, 1)
            end = dt.date(y + (month // 12), (month % 12) + 1, 1)
            qs = qs.filter(due_date__gte=start, due_date__lt=end)
            month_label = f"{month:02d}/{y}"
        else:
            start = dt.date(y, 1, 1)
            end = dt.date(y + 1, 1, 1)
            qs = qs.filter(due_date__gte=start, due_date__lt=end)
            month_label = str(y)

        rows = list(qs)
        previsto = sum((b.net_value for b in rows), Decimal("0.00"))
        recebido = sum((b.paid_value for b in rows), Decimal("0.00"))
        a_receber = sum((b.outstanding_value for b in rows), Decimal("0.00"))
        vencido = sum(
            (
                b.outstanding_value
                for b in rows
                if b.computed_status() == BillingEntry.Status.OVERDUE
            ),
            Decimal("0.00"),
        )
        return {
            "periodo": month_label,
            "quantidade_cobrancas": len(rows),
            "previsto": previsto,
            "recebido": recebido,
            "a_receber": a_receber,
            "vencido": vencido,
        }

    def finance_kpis(self, *, reference_date: dt.date | None = None) -> dict:
        """KPIs financeiros para o dashboard escolar:
        total em aberto, total vencido, recebido no mes.
        """
        from financeiro.models import BillingEntry

        reference = reference_date or dt.date.today()
        active_qs = BillingEntry.objects.exclude(status=BillingEntry.Status.CANCELLED)
        open_items = self._billings_by_computed_status(
            active_qs,
            BillingEntry.Status.OPEN,
            reference_date=reference,
        )
        overdue_items = self._billings_by_computed_status(
            active_qs,
            BillingEntry.Status.OVERDUE,
            reference_date=reference,
        )
        month_start = reference.replace(day=1)
        next_month = (
            (month_start.replace(month=12, day=1) + dt.timedelta(days=31)).replace(day=1)
            if month_start.month == 12
            else month_start.replace(month=month_start.month + 1)
        )

        received_this_month = (
            BillingEntry.objects.filter(
                payments__paid_date__gte=month_start,
                payments__paid_date__lt=next_month,
                payments__deleted_at__isnull=True,
            )
            .exclude(payments__reconciliation_status="REJECTED")
            .distinct()
            .aggregate(total=Sum("payments__amount"))
        )

        def _sum(items):
            return sum((b.outstanding_value for b in items), Decimal("0.00"))

        return {
            "total_aberto": _sum(open_items),
            "total_vencido": _sum(overdue_items),
            "recebido_mes": received_this_month["total"] or Decimal("0.00"),
        }

    @staticmethod
    def _billings_by_computed_status(qs, status: str, *, reference_date: dt.date | None = None):
        reference = reference_date or dt.date.today()
        return [
            billing for billing in qs if billing.computed_status(reference_date=reference) == status
        ]

    def _paginate(self, qs, page: int = 1, page_size: int = 20) -> PageResult:
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        page = max(1, page)
        total = qs.count()
        offset = (page - 1) * page_size
        return PageResult(
            items=list(qs[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )

    def _paginate_items(self, items: list, page: int = 1, page_size: int = 20) -> PageResult:
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        page = max(1, page)
        total = len(items)
        offset = (page - 1) * page_size
        return PageResult(
            items=items[offset : offset + page_size],
            total=total,
            page=page,
            page_size=page_size,
        )
