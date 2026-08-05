"""Parsers tolerantes para valores opcionais recebidos pela camada HTTP."""

from uuid import UUID


def parse_optional_int(value: object) -> int | None:
    """Converte um valor opcional em inteiro, retornando ``None`` quando inválido."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_optional_uuid(value: object) -> UUID | None:
    """Converte um valor opcional em UUID, retornando ``None`` quando inválido."""
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None
