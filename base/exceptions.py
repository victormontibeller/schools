"""Hierarquia de exceções da aplicação."""


class AppBaseError(Exception):
    """Raiz da hierarquia de exceções de domínio da aplicação."""

    default_message: str = "Ocorreu um erro na aplicação."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class TenantNotFoundError(AppBaseError):
    """Tenant não localizado para o domínio HTTP informado."""

    default_message = "Tenant não encontrado para o domínio informado."


class PermissionDeniedError(AppBaseError):
    """Operação bloqueada por falta de permissão do executor."""

    default_message = "Você não tem permissão para realizar esta operação."


class ValidationError(AppBaseError):
    """Falha de validação de entrada, com detalhes por campo."""

    default_message = "Os dados informados são inválidos."

    def __init__(self, message: str | None = None, errors: dict | None = None) -> None:
        super().__init__(message)
        self.errors: dict = errors or {}


class ObjectNotFoundError(AppBaseError):
    """Registro solicitado não foi encontrado pelo identificador."""

    default_message = "O registro solicitado não foi encontrado."

    def __init__(self, model_name: str = "", object_id: str = "") -> None:
        msg = (
            f"{model_name} com id '{object_id}' não encontrado."
            if model_name
            else self.default_message
        )
        super().__init__(msg)
        self.model_name = model_name
        self.object_id = object_id


class BusinessRuleViolationError(AppBaseError):
    """Operação viola uma regra de negócio do domínio."""

    default_message = "A operação viola uma regra de negócio."
