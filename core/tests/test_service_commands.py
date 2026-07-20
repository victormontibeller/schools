"""Testes dos decorators explícitos de comandos de service."""

import pytest

from base.services import system_command
from core.services import RegistrationSequenceService


@pytest.mark.django_db
def test_system_command_allows_internal_sequence_without_user():
    number = RegistrationSequenceService(user=None).next_number("student")

    assert number.startswith("ALU-")
    assert RegistrationSequenceService.next_number._service_command_kind == "system"


def test_system_command_marks_wrapped_callable():
    @system_command
    def internal_command(service):
        return service

    assert internal_command._base_service_atomic is True
    assert internal_command._service_command_kind == "system"
