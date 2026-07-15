"""Testes dos adaptadores e tarefas assíncronas financeiras."""

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from financeiro.gateway import GatewayChargeResult, ManualGateway, get_payment_gateway
from financeiro.tasks import charge_via_gateway_task, refresh_overdue_task


def test_manual_gateway_implements_complete_contract():
    gateway = get_payment_gateway()

    created = gateway.create_charge(
        billing_id="billing-1",
        amount=Decimal("10.00"),
        due_date=dt.date(2026, 7, 20),
        description="Mensalidade",
    )

    assert isinstance(gateway, ManualGateway)
    assert created == GatewayChargeResult(success=True, external_id="manual-billing-1")
    assert gateway.check_status(created.external_id) == "PENDING"
    assert gateway.cancel_charge(created.external_id).success is True


def test_refresh_overdue_task_delegates_inside_received_schema():
    service = Mock()
    service.refresh_overdue_status.return_value = 3
    with patch("financeiro.services.FinanceService", return_value=service):
        result = refresh_overdue_task.run("public")

    assert result == 3
    service.refresh_overdue_status.assert_called_once_with()


def test_charge_gateway_task_returns_external_id_and_handles_failure():
    billing = SimpleNamespace(
        pk="billing-2",
        outstanding_value=Decimal("42.00"),
        due_date=dt.date(2026, 7, 20),
        description="Parcela",
    )
    gateway = Mock()
    gateway.create_charge.return_value = GatewayChargeResult(
        success=False, external_id="external-2", error_message="indisponível"
    )
    with (
        patch("financeiro.selectors.BillingSelector.get_billing_by_id", return_value=billing),
        patch("financeiro.gateway.get_payment_gateway", return_value=gateway),
    ):
        result = charge_via_gateway_task.run("public", "billing-2")

    assert result == "external-2"
    gateway.create_charge.assert_called_once_with(
        billing_id=billing.pk,
        amount=billing.outstanding_value,
        due_date=billing.due_date,
        description=billing.description,
    )
