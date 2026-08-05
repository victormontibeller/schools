"""Testes dos decorators explícitos de comandos de service."""

import pytest

from base.services import system_command
from core.services import RegistrationSequenceService


@pytest.mark.django_db
def test_system_command_allows_internal_sequence_without_user():
    number = RegistrationSequenceService(user=None).next_number("student")

    assert number.startswith("ALU-")
    assert RegistrationSequenceService.next_number._service_command_kind == "system"


@pytest.mark.django_db
def test_system_command_creates_enrollment_application_sequence():
    from core.models import RegistrationSequence

    number = RegistrationSequenceService(user=None).next_number("enrollment_application", year=2026)

    sequence = RegistrationSequence.objects.get(scope="enrollment_application", year=2026)
    assert RegistrationSequence._meta.get_field("scope").max_length == 64
    assert number == "MAT-2026-000001"
    assert sequence.current_value == 1


def test_system_command_marks_wrapped_callable():
    @system_command
    def internal_command(service):
        return service

    assert internal_command._base_service_atomic is True
    assert internal_command._service_command_kind == "system"
