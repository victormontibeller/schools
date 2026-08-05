"""Testes do provisionamento local idempotente."""

from contextlib import nullcontext
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings

from base import context


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
    from financeiro.models import CollectionReminderPolicy, PaymentRecord
    from tenancy.models import Domain, School

    assert School.objects.filter(schema_name="public").count() == 1
    assert School.objects.filter(schema_name="demo").count() == 1
    assert Domain.objects.filter(domain="demo.localhost", is_primary=True).count() == 1
    assert Domain.objects.filter(domain="demo.localhost", tenant__schema_name="demo").count() == 1
    assert CustomUser.objects.filter(email="platform-admin@schools.local").count() == 1
    assert CustomUser.objects.filter(email="admin@demo.com").count() == 1
    demo = School.objects.get(schema_name="demo")
    assert demo.settings["student_diary"]["interactive_enabled"] is True
    assert demo.settings["timezone"] == "America/Sao_Paulo"
    assert PaymentRecord.objects.count() == 3
    assert CollectionReminderPolicy.objects.get(name="Régua DEMO desabilitada").enabled is False


@pytest.mark.django_db
@override_settings(
    DEV_PLATFORM_ADMIN_PASSWORD="PlatformTest123",
    DEV_DEMO_ADMIN_PASSWORD="DemoTest123",
)
def test_seed_dev_does_not_resave_new_administrators():
    """Contas novas já recebem senha no insert, preservando sua versão inicial."""
    with (
        patch("core.management.commands.seed_dev.schema_context", return_value=nullcontext()),
        patch("core.management.commands.seed_dev.tenant_context", return_value=nullcontext()),
        patch("core.demo_seed.DemoSeedService"),
    ):
        call_command("seed_dev")

        from core.models import CustomUser

        demo_admin = CustomUser.objects.get(email="admin@demo.com")
        platform_admin = CustomUser.objects.get(email="platform-admin@schools.local")
        assert demo_admin.version == 0
        assert platform_admin.version == 0

        call_command("seed_dev")

    demo_admin.refresh_from_db()
    platform_admin.refresh_from_db()
    assert demo_admin.version == 0
    assert platform_admin.version == 0
    assert demo_admin.check_password("DemoTest123") is True
    assert platform_admin.check_password("PlatformTest123") is True


@pytest.mark.django_db
@override_settings(
    DEV_PLATFORM_ADMIN_PASSWORD="PlatformTest123",
    DEV_DEMO_ADMIN_PASSWORD="DemoTest123",
)
def test_seed_dev_sets_demo_tenant_context_only_while_populating():
    """O seed autoriza comandos DEMO no schema ativo e restaura o contexto."""
    contexts = []

    with (
        patch("core.management.commands.seed_dev.schema_context", return_value=nullcontext()),
        patch("core.management.commands.seed_dev.tenant_context", return_value=nullcontext()),
        patch("core.demo_seed.DemoSeedService") as demo_seed_class,
    ):
        demo_seed = demo_seed_class.return_value
        demo_seed.populate_core.side_effect = lambda school: contexts.append(
            context.current_tenant.get()
        )
        demo_seed.populate_calendar.side_effect = lambda: contexts.append(
            context.current_tenant.get()
        )
        demo_seed.populate_attendance.side_effect = lambda: contexts.append(
            context.current_tenant.get()
        )
        demo_seed.populate_finance.side_effect = lambda: contexts.append(
            context.current_tenant.get()
        )

        call_command("seed_dev")

    assert contexts == ["demo", "demo", "demo", "demo"]
    assert context.current_tenant.get() == "public"
