"""Testes da fonte de data local do calendário acadêmico."""

import datetime as dt
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from academic_calendar.models import CalendarEvent
from academic_calendar.selectors import CalendarSelector


@pytest.mark.django_db
def test_upcoming_events_still_use_previous_local_day_at_utc_minus_three_boundary(user):
    """01:00 UTC ainda pertence ao dia anterior em America/Sao_Paulo."""
    utc_instant = dt.datetime(2026, 8, 5, 1, 0, tzinfo=dt.UTC)
    local_day = utc_instant.astimezone(ZoneInfo("America/Sao_Paulo")).date()
    event = CalendarEvent.objects.create(
        title="Evento na fronteira local",
        start_date=local_day,
        end_date=local_day,
        created_by=user,
        updated_by=user,
    )

    with (
        timezone.override("America/Sao_Paulo"),
        patch("django.utils.timezone.now", return_value=utc_instant),
    ):
        assert timezone.localdate() == dt.date(2026, 8, 4)
        assert list(CalendarSelector().get_upcoming_events(days=0)) == [event]
