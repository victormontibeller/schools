#!/usr/bin/env python
"""Falha quando uma página viola o contrato visual canônico."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import django

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from core.ui_contracts import check_ui_contracts  # noqa: E402


def main() -> int:
    errors = check_ui_contracts()
    if errors:
        print("Violações do contrato de UI:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Contrato de UI verificado com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
