"""Testes do ScheduleService."""

import datetime as dt

import pytest

from agenda.models import TimeSlot
from agenda.services import ScheduleService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from classes.models import Class
from core.models import CustomUser
from rooms.models import Room
from teachers.models import Subject, Teacher


def _make_user(email="agenda@test.com"):
    return CustomUser.objects.create_user(
        email=email, password="Senha123", first_name="Prof", last_name="Agenda"
    )


def _make_time_slot(user, day=TimeSlot.Day.MON):
    return TimeSlot.objects.create(
        day_of_week=day,
        start_time=dt.time(8, 0),
        end_time=dt.time(9, 0),
        slot_number=1,
        created_by=user,
        updated_by=user,
    )


def _make_subject(user):
    return Subject.objects.create(name="Matemática", code="MAT", created_by=user, updated_by=user)


def _make_teacher(user, registration="AG-001"):
    target = _make_user(f"ag-teacher{registration}@test.com")
    return Teacher.objects.create(
        user=target, registration_number=registration, created_by=user, updated_by=user
    )


_class_counter: dict[str, int] = {}


def _make_class(user):
    key = user.email
    _class_counter[key] = _class_counter.get(key, 0) + 1
    return Class.objects.create(
        name=f"1A-{_class_counter[key]}",
        grade="1º Ano",
        academic_year=2025,
        shift=Class.Shift.MORNING,
        created_by=user,
        updated_by=user,
    )


def _make_room(user, code="R-AG01"):
    return Room.objects.create(
        name=f"Sala {code}", code=code, capacity=30, created_by=user, updated_by=user
    )


@pytest.mark.django_db
class TestUpdateTimeSlot:
    def test_updates_slot_without_linked_schedule(self, user):
        slot = _make_time_slot(user)

        updated = ScheduleService(user=user).update_time_slot(
            slot.pk,
            {
                "day_of_week": TimeSlot.Day.MON,
                "slot_number": 2,
                "start_time": dt.time(9, 0),
                "end_time": dt.time(10, 0),
            },
        )

        assert updated.slot_number == 2
        assert updated.start_time == dt.time(9, 0)

    def test_rejects_slot_used_by_schedule(self, user):
        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )

        with pytest.raises(BusinessRuleViolationError):
            ScheduleService(user=user).update_time_slot(
                slot.pk,
                {
                    "day_of_week": TimeSlot.Day.MON,
                    "slot_number": 2,
                    "start_time": dt.time(9, 0),
                    "end_time": dt.time(10, 0),
                },
            )


@pytest.mark.django_db
class TestCreateSchedule:
    def test_success(self, user):
        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        schedule = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        assert schedule.pk is not None
        assert schedule.class_obj == cls

    def test_with_room(self, user):
        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        room = _make_room(user)
        schedule = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "room_id": room.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        assert schedule.room == room

    def test_missing_required_fields(self, user):
        with pytest.raises(ValidationError):
            ScheduleService(user=user).create_schedule({})

    def test_teacher_conflict_same_slot(self, user):
        cls = _make_class(user)
        cls2 = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        with pytest.raises(BusinessRuleViolationError):
            ScheduleService(user=user).create_schedule(
                {
                    "class_obj_id": cls2.pk,
                    "teacher_id": teacher.pk,
                    "subject_id": subject.pk,
                    "time_slot_id": slot.pk,
                    "valid_from": dt.date(2025, 2, 1),
                }
            )

    def test_room_conflict_same_slot(self, user):
        cls = _make_class(user)
        cls2 = _make_class(user)
        teacher1 = _make_teacher(user, "T-1")
        teacher2 = _make_teacher(user, "T-2")
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        room = _make_room(user)
        ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher1.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "room_id": room.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        with pytest.raises(BusinessRuleViolationError):
            ScheduleService(user=user).create_schedule(
                {
                    "class_obj_id": cls2.pk,
                    "teacher_id": teacher2.pk,
                    "subject_id": subject.pk,
                    "time_slot_id": slot.pk,
                    "room_id": room.pk,
                    "valid_from": dt.date(2025, 2, 1),
                }
            )

    def test_class_not_found(self, user):
        import uuid

        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        with pytest.raises(ObjectNotFoundError):
            ScheduleService(user=user).create_schedule(
                {
                    "class_obj_id": uuid.uuid4(),
                    "teacher_id": teacher.pk,
                    "subject_id": subject.pk,
                    "time_slot_id": slot.pk,
                    "valid_from": dt.date(2025, 2, 1),
                }
            )


@pytest.mark.django_db
class TestUpdateSchedule:
    def test_success(self, user):
        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        schedule = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        new_date = dt.date(2025, 3, 1)
        updated = ScheduleService(user=user).update_schedule(schedule.pk, {"valid_from": new_date})
        assert updated.valid_from == new_date

    def test_update_room(self, user):
        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        room1 = _make_room(user, "R-A")
        room2 = _make_room(user, "R-B")
        schedule = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "room_id": room1.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        updated = ScheduleService(user=user).update_schedule(schedule.pk, {"room_id": room2.pk})
        assert updated.room == room2

    def test_remove_room(self, user):
        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        room = _make_room(user, "R-C")
        schedule = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "room_id": room.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        updated = ScheduleService(user=user).update_schedule(schedule.pk, {"room_id": None})
        assert updated.room is None

    def test_update_valid_until(self, user):
        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        schedule = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        new_until = dt.date(2025, 12, 20)
        updated = ScheduleService(user=user).update_schedule(
            schedule.pk, {"valid_until": new_until}
        )
        assert updated.valid_until == new_until

    def test_update_teacher(self, user):
        cls = _make_class(user)
        teacher1 = _make_teacher(user, "T-O")
        teacher2 = _make_teacher(user, "T-N")
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        schedule = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher1.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        updated = ScheduleService(user=user).update_schedule(
            schedule.pk, {"teacher_id": teacher2.pk}
        )
        assert updated.teacher == teacher2

    def test_update_invalid_timeslot(self, user):
        import uuid

        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        schedule = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        with pytest.raises(ObjectNotFoundError):
            ScheduleService(user=user).update_schedule(schedule.pk, {"time_slot_id": uuid.uuid4()})

    def test_update_invalid_teacher(self, user):
        import uuid

        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        schedule = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        with pytest.raises(ObjectNotFoundError):
            ScheduleService(user=user).update_schedule(schedule.pk, {"teacher_id": uuid.uuid4()})

    def test_update_invalid_room(self, user):
        import uuid

        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        schedule = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        with pytest.raises(ObjectNotFoundError):
            ScheduleService(user=user).update_schedule(schedule.pk, {"room_id": uuid.uuid4()})

    def test_conflict_on_update(self, user):
        cls = _make_class(user)
        cls2 = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot1 = _make_time_slot(user, TimeSlot.Day.MON)
        slot2 = TimeSlot.objects.create(
            day_of_week=TimeSlot.Day.TUE,
            start_time=dt.time(8, 0),
            end_time=dt.time(9, 0),
            slot_number=1,
            created_by=user,
            updated_by=user,
        )
        ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot1.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        s2 = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls2.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot2.pk,
                "valid_from": dt.date(2025, 3, 1),
            }
        )
        with pytest.raises(BusinessRuleViolationError):
            ScheduleService(user=user).update_schedule(s2.pk, {"time_slot_id": slot1.pk})


@pytest.mark.django_db
class TestCreateTimeSlot:
    def test_success(self, user):
        slot = ScheduleService(user=user).create_time_slot(
            {
                "day_of_week": TimeSlot.Day.MON,
                "start_time": dt.time(8, 0),
                "end_time": dt.time(9, 0),
                "slot_number": 1,
            }
        )
        assert slot.pk is not None
        assert slot.day_of_week == TimeSlot.Day.MON

    def test_invalid_time_range(self, user):
        with pytest.raises(ValidationError):
            ScheduleService(user=user).create_time_slot(
                {
                    "day_of_week": TimeSlot.Day.MON,
                    "start_time": dt.time(10, 0),
                    "end_time": dt.time(9, 0),
                }
            )

    def test_duplicate_time_slot(self, user):
        data = {
            "day_of_week": TimeSlot.Day.MON,
            "start_time": dt.time(8, 0),
            "end_time": dt.time(9, 0),
        }
        ScheduleService(user=user).create_time_slot(data)
        with pytest.raises(ValidationError):
            ScheduleService(user=user).create_time_slot(data)

    def test_missing_required(self, user):
        with pytest.raises(ValidationError):
            ScheduleService(user=user).create_time_slot({"day_of_week": TimeSlot.Day.MON})


@pytest.mark.django_db
class TestGroupByDayOfWeek:
    def test_groups_correctly(self, user):
        from agenda.selectors import ScheduleSelector

        slot_mon = _make_time_slot(user, TimeSlot.Day.MON)
        slot_tue = TimeSlot.objects.create(
            day_of_week=TimeSlot.Day.TUE,
            start_time=dt.time(9, 0),
            end_time=dt.time(10, 0),
            slot_number=1,
            created_by=user,
            updated_by=user,
        )
        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        s1 = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot_mon.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        s2 = ScheduleService(user=user).create_schedule(
            {
                "class_obj_id": cls.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "time_slot_id": slot_tue.pk,
                "valid_from": dt.date(2025, 2, 1),
            }
        )
        by_day = ScheduleSelector.group_by_day_of_week([s1, s2])
        assert len(by_day["MON"]) == 1
        assert len(by_day["TUE"]) == 1
        assert len(by_day["WED"]) == 0


@pytest.mark.django_db
class TestCreateScheduleErrors:
    def test_class_not_found(self, user):
        import uuid

        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        with pytest.raises(ObjectNotFoundError):
            ScheduleService(user=user).create_schedule(
                {
                    "class_obj_id": uuid.uuid4(),
                    "teacher_id": teacher.pk,
                    "subject_id": subject.pk,
                    "time_slot_id": slot.pk,
                    "valid_from": dt.date(2025, 2, 1),
                }
            )

    def test_teacher_not_found(self, user):
        import uuid

        cls = _make_class(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        with pytest.raises(ObjectNotFoundError):
            ScheduleService(user=user).create_schedule(
                {
                    "class_obj_id": cls.pk,
                    "teacher_id": uuid.uuid4(),
                    "subject_id": subject.pk,
                    "time_slot_id": slot.pk,
                    "valid_from": dt.date(2025, 2, 1),
                }
            )

    def test_subject_not_found(self, user):
        import uuid

        cls = _make_class(user)
        teacher = _make_teacher(user)
        slot = _make_time_slot(user)
        with pytest.raises(ObjectNotFoundError):
            ScheduleService(user=user).create_schedule(
                {
                    "class_obj_id": cls.pk,
                    "teacher_id": teacher.pk,
                    "subject_id": uuid.uuid4(),
                    "time_slot_id": slot.pk,
                    "valid_from": dt.date(2025, 2, 1),
                }
            )

    def test_time_slot_not_found(self, user):
        import uuid

        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        with pytest.raises(ObjectNotFoundError):
            ScheduleService(user=user).create_schedule(
                {
                    "class_obj_id": cls.pk,
                    "teacher_id": teacher.pk,
                    "subject_id": subject.pk,
                    "time_slot_id": uuid.uuid4(),
                    "valid_from": dt.date(2025, 2, 1),
                }
            )

    def test_room_not_found(self, user):
        import uuid

        cls = _make_class(user)
        teacher = _make_teacher(user)
        subject = _make_subject(user)
        slot = _make_time_slot(user)
        with pytest.raises(ObjectNotFoundError):
            ScheduleService(user=user).create_schedule(
                {
                    "class_obj_id": cls.pk,
                    "teacher_id": teacher.pk,
                    "subject_id": subject.pk,
                    "time_slot_id": slot.pk,
                    "valid_from": dt.date(2025, 2, 1),
                    "room_id": uuid.uuid4(),
                }
            )
