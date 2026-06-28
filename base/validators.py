"""BaseValidator: validação de entrada com acúmulo de erros."""

from base.exceptions import ValidationError


class BaseValidator:
    """Base para validadores que acumulam erros antes de disparar exceção."""

    def __init__(self) -> None:
        self._errors: dict[str, list[str]] = {}

    def add_error(self, field: str, message: str) -> None:
        """Acumula uma mensagem de erro para o campo informado."""
        self._errors.setdefault(field, []).append(message)

    def raise_if_errors(self) -> None:
        """Lança `ValidationError` caso existam erros acumulados."""
        if self._errors:
            raise ValidationError(errors=self._errors)

    def validate(self, data: dict) -> None:
        """Valida os dados informados; subclasses devem implementar."""
        raise NotImplementedError
