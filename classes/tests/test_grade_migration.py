"""Testes da normalização de séries legadas."""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    ("legacy", "expected"),
    [
        ("1º Ano", "ELEMENTARY_1"),
        ("6º ano", "ELEMENTARY_6"),
        ("9o ANO", "ELEMENTARY_9"),
        ("1ª série", "HIGH_SCHOOL_1"),
        ("Pré II", "EARLY_PRE_2"),
        ("Outra", "OTHER"),
    ],
)
def test_normalize_grade_value_converts_known_aliases(legacy, expected):
    migration = import_module("classes.migrations.0004_structured_class_grade")

    assert migration.normalize_grade_value(legacy) == expected


def test_normalize_grade_value_preserves_unknown_legacy_value():
    migration = import_module("classes.migrations.0004_structured_class_grade")

    assert migration.normalize_grade_value("Série Experimental") == "Série Experimental"
