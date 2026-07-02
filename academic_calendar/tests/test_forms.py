"""Testes dos formularios do calendario academico."""

from academic_calendar.forms import EventForm


def test_event_form_exposes_recurrence_configuration():
    form = EventForm()

    assert "recurrence" in form.fields
    assert form.fields["recurrence"].widget.attrs["rows"] == 3
