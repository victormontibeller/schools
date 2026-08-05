"""Testes dos parsers opcionais compartilhados."""

import uuid

import pytest

from base.parsers import parse_optional_int, parse_optional_uuid


@pytest.mark.parametrize("value", [None, "", "inválido", object()])
def test_parse_optional_int_returns_none_when_value_is_absent_or_invalid(value) -> None:
    assert parse_optional_int(value) is None


@pytest.mark.parametrize(("value", "expected"), [("0", 0), ("42", 42), (-3, -3)])
def test_parse_optional_int_returns_integer_when_value_is_valid(value, expected) -> None:
    assert parse_optional_int(value) == expected


def test_parse_optional_uuid_returns_uuid_when_value_is_valid() -> None:
    expected = uuid.uuid4()
    assert parse_optional_uuid(str(expected)) == expected
    assert parse_optional_uuid(expected) == expected


@pytest.mark.parametrize("value", [None, "", "inválido", object()])
def test_parse_optional_uuid_returns_none_when_value_is_absent_or_invalid(value) -> None:
    assert parse_optional_uuid(value) is None
