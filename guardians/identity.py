"""Tradução da unicidade ativa de CPF sem expor o valor ou detalhes do banco."""

from contextlib import contextmanager

from django.db import IntegrityError, transaction

from base.exceptions import BusinessRuleViolationError


@contextmanager
def guardian_identity_write():
    try:
        with transaction.atomic():
            yield
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
        if constraint == "guardian_active_cpf_unique" or "guardians_guardian.cpf" in str(exc):
            raise BusinessRuleViolationError(
                "Outro cadastro ativo já utiliza este CPF. Reconcilie a identidade do responsável."
            ) from None
        raise
