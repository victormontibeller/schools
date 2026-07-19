"""Testes do shell canônico e do catálogo de UI."""

from core.ui_contracts import check_ui_contracts


def test_ui_contracts_have_no_violations() -> None:
    assert check_ui_contracts() == []
