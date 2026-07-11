"""Testes dos formularios do calendario academico."""

from academic_calendar.forms import EventForm


def test_event_form_exposes_only_calendar_fields():
    form = EventForm()

    assert "description" in form.fields
    assert form.fields["description"].widget.__class__.__name__ == "TextInput"
    for field_name in ("start_time", "end_time", "recurrence", "academic_year"):
        assert field_name not in form.fields
