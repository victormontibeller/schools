"""Testes do dispatcher tenant-scoped da régua financeira."""

from unittest.mock import patch

import pytest

from core import settings as project_settings
from financeiro.tasks import dispatch_collection_reminders_task
from tenancy.models import School


@pytest.mark.django_db
def test_dispatcher_publishes_each_active_non_public_schema_and_continues_after_failure(user):
    """Falha em uma escola não interrompe as publicações das demais."""
    School.objects.create(
        name="Public",
        schema_name="public",
        created_by=user,
        updated_by=user,
    )
    School.objects.create(
        name="Escola A",
        schema_name="school_a",
        created_by=user,
        updated_by=user,
    )
    School.objects.create(
        name="Escola B",
        schema_name="school_b",
        created_by=user,
        updated_by=user,
    )
    inactive = School.objects.create(
        name="Escola Inativa",
        schema_name="inactive",
        created_by=user,
        updated_by=user,
    )
    inactive.soft_delete(user=user)

    with patch("financeiro.tasks.process_collection_reminders_task.delay") as delay:
        delay.side_effect = [ConnectionError("broker unavailable"), None]
        assert dispatch_collection_reminders_task.run() == 1

    assert [call.args for call in delay.call_args_list] == [("school_a",), ("school_b",)]


def test_beat_schedules_only_enrollment_recovery_and_financial_dispatcher():
    """Beat não agenda expiração DEMO nem atualização de dashboards neste pacote."""
    schedule = project_settings.CELERY_BEAT_SCHEDULE

    assert {entry["task"] for entry in schedule.values()} == {
        "enrollments.dispatch_stale_document_reminder_recovery",
        "financeiro.dispatch_collection_reminders",
    }
    financial = schedule["dispatch-daily-collection-reminders"]["schedule"]
    assert str(financial) == "<crontab: 0 8 * * * (m/h/dM/MY/d)>"
    assert project_settings.CELERY_TIMEZONE == "America/Sao_Paulo"
