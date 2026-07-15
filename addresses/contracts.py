"""Contrato público do domínio de endereços."""

from addresses.models import (
    Address,
    BusinessUnitAddress,
    GuardianAddress,
    SchoolAddress,
    StudentAddress,
    TeacherAddress,
)

__all__ = [
    "Address",
    "BusinessUnitAddress",
    "GuardianAddress",
    "SchoolAddress",
    "StudentAddress",
    "TeacherAddress",
]
