"""Testes do CalendarService."""

import datetime as dt

import pytest

from academic_calendar.models import AcademicYear, CalendarEvent, Holiday
from academic_calendar.services import CalendarService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from classes.models import Class


@pytest.mark.django_db
class TestCreateAcademicYear:
    def test_success(self, user):
        ay = CalendarService(user=user).create_academic_year(
            {"name": "2025", "start_date": dt.date(2025, 2, 1), "end_date": dt.date(2025, 12, 20)}
        )
        assert ay.pk is not None
        assert ay.name == "2025"
        assert ay.status == AcademicYear.Status.PLANNED

    def test_invalid_date_range(self, user):
        with pytest.raises(ValidationError):
            CalendarService(user=user).create_academic_year(
                {
                    "name": "2025",
                    "start_date": dt.date(2025, 12, 1),
                    "end_date": dt.date(2025, 1, 1),
                }
            )

    def test_missing_required_fields(self, user):
        with pytest.raises(ValidationError):
            CalendarService(user=user).create_academic_year({"name": "2025"})

    def test_duplicate_name_start(self, user):
        CalendarService(user=user).create_academic_year(
            {"name": "2025", "start_date": dt.date(2025, 2, 1), "end_date": dt.date(2025, 12, 20)}
        )
        with pytest.raises(ValidationError):
            CalendarService(user=user).create_academic_year(
                {
                    "name": "2025",
                    "start_date": dt.date(2025, 2, 1),
                    "end_date": dt.date(2025, 12, 20),
                }
            )


@pytest.mark.django_db
class TestCreateEvent:
    def test_missing_required_fields(self, user):
        with pytest.raises(ValidationError):
            CalendarService(user=user).create_event({})

    def test_success(self, user):
        event = CalendarService(user=user).create_event(
            {
                "title": "Reunião de Pais",
                "start_date": dt.date(2025, 3, 15),
                "end_date": dt.date(2025, 3, 15),
                "type": CalendarEvent.Type.MEETING,
            }
        )
        assert event.pk is not None
        assert event.title == "Reunião de Pais"

    def test_with_audience_class_missing_class_obj(self, user):
        with pytest.raises(ValidationError):
            CalendarService(user=user).create_event(
                {
                    "title": "Evento Turma",
                    "start_date": dt.date(2025, 3, 15),
                    "end_date": dt.date(2025, 3, 15),
                    "type": CalendarEvent.Type.SCHOOL_EVENT,
                    "audience": CalendarEvent.Audience.CLASS,
                }
            )

    def test_with_class_obj(self, user):
        cls = Class.objects.create(
            name="1A",
            grade="1º Ano",
            academic_year=2025,
            shift=Class.Shift.MORNING,
            created_by=user,
            updated_by=user,
        )
        event = CalendarService(user=user).create_event(
            {
                "title": "Evento 1A",
                "start_date": dt.date(2025, 3, 15),
                "end_date": dt.date(2025, 3, 15),
                "type": CalendarEvent.Type.SCHOOL_EVENT,
                "audience": CalendarEvent.Audience.CLASS,
                "class_obj_id": cls.pk,
            }
        )
        assert event.class_obj == cls

    def test_invalid_date_range(self, user):
        with pytest.raises(ValidationError):
            CalendarService(user=user).create_event(
                {
                    "title": "Evento Inválido",
                    "start_date": dt.date(2025, 3, 15),
                    "end_date": dt.date(2025, 3, 10),
                    "type": CalendarEvent.Type.SCHOOL_EVENT,
                }
            )

    def test_with_academic_year(self, user):
        ay = AcademicYear.objects.create(
            name="2025",
            start_date=dt.date(2025, 2, 1),
            end_date=dt.date(2025, 12, 20),
            created_by=user,
            updated_by=user,
        )
        event = CalendarService(user=user).create_event(
            {
                "title": "Evento Anual",
                "start_date": dt.date(2025, 3, 15),
                "end_date": dt.date(2025, 3, 15),
                "type": CalendarEvent.Type.SCHOOL_EVENT,
                "academic_year_id": ay.pk,
            }
        )
        assert event.academic_year == ay


@pytest.mark.django_db
class TestUpdateEvent:
    def test_success(self, user):
        event = CalendarService(user=user).create_event(
            {
                "title": "Evento Original",
                "start_date": dt.date(2025, 3, 15),
                "end_date": dt.date(2025, 3, 15),
                "type": CalendarEvent.Type.MEETING,
            }
        )
        updated = CalendarService(user=user).update_event(
            event.pk, {"title": "Evento Atualizado", "is_public": True}
        )
        assert updated.title == "Evento Atualizado"
        assert updated.is_public is True


@pytest.mark.django_db
class TestUpdateEventErrors:
    def test_invalid_date_range(self, user):
        event = CalendarService(user=user).create_event(
            {
                "title": "Evento",
                "start_date": dt.date(2025, 3, 15),
                "end_date": dt.date(2025, 3, 15),
                "type": CalendarEvent.Type.MEETING,
            }
        )
        with pytest.raises(ValidationError):
            CalendarService(user=user).update_event(
                event.pk, {"start_date": dt.date(2025, 3, 20), "end_date": dt.date(2025, 3, 10)}
            )

    def test_set_class_obj(self, user):
        event = CalendarService(user=user).create_event(
            {
                "title": "Evento",
                "start_date": dt.date(2025, 3, 15),
                "end_date": dt.date(2025, 3, 15),
                "type": CalendarEvent.Type.MEETING,
            }
        )
        cls = Class.objects.create(
            name="Cal-A",
            grade="1º Ano",
            academic_year=2025,
            shift=Class.Shift.MORNING,
            created_by=user,
            updated_by=user,
        )
        updated = CalendarService(user=user).update_event(event.pk, {"class_obj_id": cls.pk})
        assert updated.class_obj == cls

    def test_unset_class_obj(self, user):
        cls = Class.objects.create(
            name="Cal-B",
            grade="1º Ano",
            academic_year=2025,
            shift=Class.Shift.MORNING,
            created_by=user,
            updated_by=user,
        )
        event = CalendarService(user=user).create_event(
            {
                "title": "Evento com Turma",
                "start_date": dt.date(2025, 3, 15),
                "end_date": dt.date(2025, 3, 15),
                "type": CalendarEvent.Type.SCHOOL_EVENT,
                "class_obj_id": cls.pk,
            }
        )
        updated = CalendarService(user=user).update_event(event.pk, {"class_obj_id": None})
        assert updated.class_obj is None

    def test_invalid_class_obj(self, user):
        import uuid

        event = CalendarService(user=user).create_event(
            {
                "title": "Evento",
                "start_date": dt.date(2025, 3, 15),
                "end_date": dt.date(2025, 3, 15),
                "type": CalendarEvent.Type.MEETING,
            }
        )
        with pytest.raises(ValidationError):
            CalendarService(user=user).update_event(event.pk, {"class_obj_id": uuid.uuid4()})


@pytest.mark.django_db
class TestCancelEvent:
    def test_success(self, user):
        event = CalendarService(user=user).create_event(
            {
                "title": "Evento Cancelável",
                "start_date": dt.date(2025, 3, 15),
                "end_date": dt.date(2025, 3, 15),
                "type": CalendarEvent.Type.MEETING,
            }
        )
        result = CalendarService(user=user).cancel_event(event.pk, "Motivo X")
        assert result.is_cancelled is True
        assert result.cancel_reason == "Motivo X"

    def test_already_cancelled(self, user):
        event = CalendarService(user=user).create_event(
            {
                "title": "Evento Já Cancelado",
                "start_date": dt.date(2025, 3, 15),
                "end_date": dt.date(2025, 3, 15),
                "type": CalendarEvent.Type.MEETING,
            }
        )
        CalendarService(user=user).cancel_event(event.pk)
        with pytest.raises(BusinessRuleViolationError):
            CalendarService(user=user).cancel_event(event.pk)


@pytest.mark.django_db
class TestCreateHoliday:
    def test_success(self, user):
        holiday = CalendarService(user=user).create_holiday(
            {
                "name": "Independência",
                "date": dt.date(2025, 9, 7),
                "type": Holiday.Type.NATIONAL,
            }
        )
        assert holiday.pk is not None
        assert holiday.name == "Independência"

    def test_duplicate(self, user):
        data = {
            "name": "Natal",
            "date": dt.date(2025, 12, 25),
            "type": Holiday.Type.NATIONAL,
        }
        CalendarService(user=user).create_holiday(data)
        with pytest.raises(ValidationError):
            CalendarService(user=user).create_holiday(data)

    def test_missing_required(self, user):
        with pytest.raises(ValidationError):
            CalendarService(user=user).create_holiday({"name": "Sem data"})

    def test_recurring(self, user):
        holiday = CalendarService(user=user).create_holiday(
            {
                "name": "Natal",
                "date": dt.date(2025, 12, 25),
                "type": Holiday.Type.NATIONAL,
                "is_recurring": True,
            }
        )
        assert holiday.is_recurring is True


@pytest.mark.django_db
class TestWorkingDays:
    def test_is_working_day_weekday(self, user):
        monday = dt.date(2025, 3, 10)
        assert CalendarService(user=user).is_working_day(monday) is True

    def test_is_not_working_day_weekend(self, user):
        saturday = dt.date(2025, 3, 8)
        assert CalendarService(user=user).is_working_day(saturday) is False

    def test_is_not_working_day_holiday(self, user):
        Holiday.objects.create(
            name="Feriado Teste",
            date=dt.date(2025, 4, 21),
            type=Holiday.Type.NATIONAL,
            created_by=user,
            updated_by=user,
        )
        assert CalendarService(user=user).is_working_day(dt.date(2025, 4, 21)) is False

    def test_get_working_days(self, user):
        start = dt.date(2025, 3, 10)
        end = dt.date(2025, 3, 14)
        days = CalendarService(user=user).get_working_days(start, end)
        assert len(days) == 5  # Segunda a Sexta

    def test_get_working_days_with_holiday(self, user):
        Holiday.objects.create(
            name="Feriado",
            date=dt.date(2025, 3, 12),
            type=Holiday.Type.NATIONAL,
            created_by=user,
            updated_by=user,
        )
        days = CalendarService(user=user).get_working_days(
            dt.date(2025, 3, 10), dt.date(2025, 3, 14)
        )
        assert len(days) == 4

    def test_get_working_days_invalid_range(self, user):
        with pytest.raises(ValidationError):
            CalendarService(user=user).get_working_days(dt.date(2025, 3, 15), dt.date(2025, 3, 10))

    def test_is_working_day_recurring_holiday(self, user):
        Holiday.objects.create(
            name="Natal",
            date=dt.date(2025, 12, 25),
            type=Holiday.Type.NATIONAL,
            is_recurring=True,
            created_by=user,
            updated_by=user,
        )
        assert CalendarService(user=user).is_working_day(dt.date(2024, 12, 25)) is False

    def test_is_working_day_non_school_day_event(self, user):
        CalendarEvent.objects.create(
            title="Dia não letivo",
            start_date=dt.date(2025, 5, 1),
            end_date=dt.date(2025, 5, 1),
            type=CalendarEvent.Type.NON_SCHOOL_DAY,
            created_by=user,
            updated_by=user,
        )
        assert CalendarService(user=user).is_working_day(dt.date(2025, 5, 1)) is False


@pytest.mark.django_db
class TestCreateEventErrors:
    def test_invalid_class_obj(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            CalendarService(user=user).create_event(
                {
                    "title": "Evento",
                    "start_date": dt.date(2025, 3, 15),
                    "end_date": dt.date(2025, 3, 15),
                    "type": CalendarEvent.Type.SCHOOL_EVENT,
                    "class_obj_id": uuid.uuid4(),
                }
            )

    def test_invalid_academic_year(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            CalendarService(user=user).create_event(
                {
                    "title": "Evento",
                    "start_date": dt.date(2025, 3, 15),
                    "end_date": dt.date(2025, 3, 15),
                    "type": CalendarEvent.Type.SCHOOL_EVENT,
                    "academic_year_id": uuid.uuid4(),
                }
            )


@pytest.mark.django_db
class TestMonthGrid:
    def test_empty_month(self, user):
        from academic_calendar.selectors import CalendarSelector

        grid = CalendarSelector().get_month_grid(2025, 3)
        assert len(grid["weeks"]) == 6
        assert len(grid["weeks"][0]) == 7
        assert grid["month_name"] is not None
        assert grid["prev_year"] == 2025
        assert grid["prev_month"] == 2
