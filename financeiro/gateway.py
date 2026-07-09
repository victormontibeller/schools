"""Adaptador de gateway de pagamento — ponto unico de integracao externa.

Design: interface `PaymentGateway` (porta) com implementacoes que encapsulam
provedores externos. As tasks/services dependem apenas da interface, nunca do
provedor concreto. Operacao 100% manual permanece disponivel: a implementacao
`ManualGateway` (default) apenas registra a intencao, sem chamada externa.

Quando um provedor real for integrado (ex: Stripe/PagSeguro), basta adicionar
uma nova implementacao e injeta-la via `core/settings` ou factory — sem tocar
as tasks/services que dependem de `PaymentGateway`.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GatewayChargeResult:
    """Resultado da criacao de uma cobranca no gateway."""

    success: bool
    external_id: str = ""
    error_message: str = ""


class PaymentGateway(ABC):
    """Porta (interface) para gateway de pagamento externo.

    Toda implementacao encapsula credenciais e protocolo do provedor.
    Tasks e services dependem desta interface, nunca do provedor concreto.
    """

    gateway_name: str = ""

    @abstractmethod
    def create_charge(
        self, *, billing_id, amount, due_date, description: str
    ) -> GatewayChargeResult:
        """Cria a cobranca no provedor e retorna o identificador externo."""
        ...

    @abstractmethod
    def check_status(self, external_id: str) -> str:
        """Consulta o status atual da cobranca no provedor. Retorna um label."""
        ...

    @abstractmethod
    def cancel_charge(self, external_id: str) -> GatewayChargeResult:
        """Cancela a cobranca no provedor."""
        ...


class ManualGateway(PaymentGateway):
    """Gateway manual (fallback) — nao integra provedor externo.

    Registra a intencao em log apenas. Permite operacao 100% manual enquanto
    nenhum provedor real e configurado.
    """

    gateway_name = "MANUAL"

    def create_charge(
        self, *, billing_id, amount, due_date, description: str
    ) -> GatewayChargeResult:
        logger.info(
            "Cobranca manual registrada (sem integracao externa)",
            extra={
                "billing_id": str(billing_id),
                "amount": str(amount),
                "due_date": (
                    due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date)
                ),
            },
        )
        return GatewayChargeResult(success=True, external_id=f"manual-{billing_id}")

    def check_status(self, external_id: str) -> str:
        return "PENDING"

    def cancel_charge(self, external_id: str) -> GatewayChargeResult:
        return GatewayChargeResult(success=True, external_id=external_id)


# Factory simples — injeta o gateway configurado. Retorna ManualGateway por
# default; em prod_um provedor real pode ser injetado via env.
def get_payment_gateway() -> PaymentGateway:
    """Retorna o gateway de pagamento configurado. Default: ManualGateway."""
    return ManualGateway()
