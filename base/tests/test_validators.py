"""Testes para base.validators (CPF, UF, CEP)."""

import pytest
from django.core.exceptions import ValidationError

from base.validators import validate_cep, validate_cnpj, validate_cpf, validate_uf


class TestValidateCPF:
    def test_valid_cpf(self):
        result = validate_cpf("52998224725")
        assert result == "52998224725"

    def test_valid_cpf_formatted(self):
        result = validate_cpf("529.982.247-25")
        assert result == "52998224725"

    def test_invalid_digits(self):
        with pytest.raises(ValidationError):
            validate_cpf("52998224726")

    def test_all_same_digits(self):
        with pytest.raises(ValidationError):
            validate_cpf("11111111111")

    def test_too_short(self):
        with pytest.raises(ValidationError):
            validate_cpf("123")

    def test_too_long(self):
        with pytest.raises(ValidationError):
            validate_cpf("123456789012")

    def test_empty(self):
        assert validate_cpf("") == ""

    def test_second_check_digit_invalid(self):
        cpf = "52998224724"  # mudando o ultimo digito de 5 para 4 = invalido
        with pytest.raises(ValidationError):
            validate_cpf(cpf)


class TestValidateUF:
    def test_valid_uf(self):
        assert validate_uf("SP") == "SP"
        assert validate_uf("rj") == "RJ"
        assert validate_uf("  mg  ") == "MG"

    def test_invalid_uf(self):
        with pytest.raises(ValidationError):
            validate_uf("XX")

    def test_empty(self):
        assert validate_uf("") == ""

    def test_all_valid_ufs(self):
        valid = [
            "AC",
            "AL",
            "AP",
            "AM",
            "BA",
            "CE",
            "DF",
            "ES",
            "GO",
            "MA",
            "MT",
            "MS",
            "MG",
            "PA",
            "PB",
            "PR",
            "PE",
            "PI",
            "RJ",
            "RN",
            "RS",
            "RO",
            "RR",
            "SC",
            "SP",
            "SE",
            "TO",
        ]
        for uf in valid:
            assert validate_uf(uf) == uf


class TestValidateCEP:
    def test_valid_cep(self):
        assert validate_cep("01001000") == "01001000"

    def test_valid_cep_formatted(self):
        assert validate_cep("01001-000") == "01001000"

    def test_invalid_short(self):
        with pytest.raises(ValidationError):
            validate_cep("123")

    def test_invalid_long(self):
        with pytest.raises(ValidationError):
            validate_cep("123456789")

    def test_empty(self):
        assert validate_cep("") == ""


class TestValidateCNPJ:
    def test_valid_cnpj(self):
        result = validate_cnpj("11222333000181")
        assert result == "11222333000181"

    def test_valid_cnpj_formatted(self):
        result = validate_cnpj("11.222.333/0001-81")
        assert result == "11222333000181"

    def test_invalid_digits(self):
        with pytest.raises(ValidationError):
            validate_cnpj("11222333000182")

    def test_all_same_digits(self):
        with pytest.raises(ValidationError):
            validate_cnpj("11111111111111")

    def test_too_short(self):
        with pytest.raises(ValidationError):
            validate_cnpj("123")

    def test_too_long(self):
        with pytest.raises(ValidationError):
            validate_cnpj("123456789012345")

    def test_empty(self):
        assert validate_cnpj("") == ""

    def test_cnpj_formatted_with_special_chars(self):
        result = validate_cnpj("  11.222.333/0001-81  ")
        assert result == "11222333000181"
