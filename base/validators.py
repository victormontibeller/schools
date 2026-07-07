"""Validadores reutilizaveis: CPF, CEP, UF e formatos brasileiros."""

import re

from django.core.exceptions import ValidationError as DjangoValidationError


def validate_cpf(value: str) -> str:
    """Valida formato e digitos verificadores de CPF.

    Returns:
        CPF apenas com digitos (11 caracteres).
    """
    if not value:
        return value

    cpf = re.sub(r"[^0-9]", "", value)

    if len(cpf) != 11:
        raise DjangoValidationError("CPF deve conter 11 digitos.")

    if cpf == cpf[0] * 11:
        raise DjangoValidationError("CPF invalido (todos os digitos iguais).")

    total = sum(int(cpf[i]) * (10 - i) for i in range(9))
    remainder = (total * 10) % 11
    if remainder == 10:
        remainder = 0
    if remainder != int(cpf[9]):
        raise DjangoValidationError("CPF invalido (primeiro digito verificador).")

    total = sum(int(cpf[i]) * (11 - i) for i in range(10))
    remainder = (total * 10) % 11
    if remainder == 10:
        remainder = 0
    if remainder != int(cpf[10]):
        raise DjangoValidationError("CPF invalido (segundo digito verificador).")

    return cpf


def validate_uf(value: str) -> str:
    """Valida que o valor corresponde a uma UF brasileira valida.

    Returns:
        UF em maiusculas (2 caracteres).
    """
    from locations.models import State

    if not value:
        return value
    uf = value.strip().upper()
    if not State.objects.filter(code=uf).exists():
        raise DjangoValidationError(f"UF invalida: '{value}'. Use a sigla de 2 letras.")
    return uf


def validate_cep(value: str) -> str:
    """Valida formato de CEP (8 digitos).

    Returns:
        CEP apenas com digitos (8 caracteres).
    """
    if not value:
        return value
    cep = re.sub(r"[^0-9]", "", value)
    if len(cep) != 8:
        raise DjangoValidationError("CEP deve conter 8 digitos.")
    return cep


def validate_cnpj(value: str) -> str:
    """Valida formato e digitos verificadores de CNPJ.

    Returns:
        CNPJ apenas com digitos (14 caracteres).
    """
    if not value:
        return value

    cnpj = re.sub(r"[^0-9]", "", value)

    if len(cnpj) != 14:
        raise DjangoValidationError("CNPJ deve conter 14 digitos.")

    if cnpj == cnpj[0] * 14:
        raise DjangoValidationError("CNPJ invalido (todos os digitos iguais).")

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto = total % 11
    dv1 = 0 if resto < 2 else 11 - resto
    if dv1 != int(cnpj[12]):
        raise DjangoValidationError("CNPJ invalido (primeiro digito verificador).")

    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto = total % 11
    dv2 = 0 if resto < 2 else 11 - resto
    if dv2 != int(cnpj[13]):
        raise DjangoValidationError("CNPJ invalido (segundo digito verificador).")

    return cnpj
