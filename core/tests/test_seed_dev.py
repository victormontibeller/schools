"""Testes do provisionamento local idempotente."""

from contextlib import nullcontext
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings


@pytest.mark.django_db
@override_settings(
    DEV_PLATFORM_ADMIN_PASSWORD="PlatformTest123",
    DEV_DEMO_ADMIN_PASSWORD="DemoTest123",
)
def test_seed_dev_is_idempotent_and_creates_platform_and_demo_accounts():
    with (
        patch("core.management.commands.seed_dev.schema_context", return_value=nullcontext()),
        patch("core.management.commands.seed_dev.tenant_context", return_value=nullcontext()),
    ):
        call_command("seed_dev")
        call_command("seed_dev")

    from core.models import CustomUser
    from tenancy.models import Domain, School

    assert School.objects.filter(schema_name="public").count() == 1
    assert School.objects.filter(schema_name="demo").count() == 1
    assert Domain.objects.filter(domain="demo.localhost", is_primary=True).count() == 1
    assert Domain.objects.filter(domain="demo.localhost", tenant__schema_name="demo").count() == 1
    assert CustomUser.objects.filter(email="platform-admin@schools.local").count() == 1
    assert CustomUser.objects.filter(email="admin@demo.com").count() == 1
