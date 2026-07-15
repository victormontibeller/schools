"""Garantias transacionais da publicação assíncrona de calendário."""

import logging
from unittest.mock import patch

import pytest
from django.db import transaction

from base.events import DomainEvent
from notifications.handlers import _handle_calendar_event_created


class _CalendarEvent:
    audience = "ALL"
    title = "Reunião"
    description = "Comunicado institucional"
    start_date = "2026-07-14"


def _event() -> DomainEvent:
    return DomainEvent(
        operation="INSERT",
        instance=_CalendarEvent(),
        user=None,
        correlation_id="corr-123",
    )


@pytest.mark.django_db(transaction=True)
def test_calendar_task_is_published_only_after_commit():
    with patch("notifications.tasks.notify_audience_all_task.delay") as delay:
        with transaction.atomic():
            _handle_calendar_event_created(_event())
            delay.assert_not_called()
        delay.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_calendar_task_is_discarded_on_rollback():
    with patch("notifications.tasks.notify_audience_all_task.delay") as delay:
        with pytest.raises(RuntimeError), transaction.atomic():
            _handle_calendar_event_created(_event())
            raise RuntimeError("rollback")
        delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_calendar_task_is_immediate_without_active_transaction():
    with patch("notifications.tasks.notify_audience_all_task.delay") as delay:
        _handle_calendar_event_created(_event())
        delay.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_broker_failure_after_commit_is_logged_without_escaping(caplog):
    caplog.set_level(logging.ERROR, logger="notifications.handlers")
    with patch(
        "notifications.tasks.notify_audience_all_task.delay",
        side_effect=ConnectionError("broker unavailable"),
    ):
        with transaction.atomic():
            _handle_calendar_event_created(_event())

    assert "Falha ao publicar notificacao de calendario" in caplog.text
