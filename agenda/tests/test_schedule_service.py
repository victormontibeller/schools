"""Testes das regras e do versionamento da matriz de horários."""

import datetime as dt

import pytest

from activities.services import ActivityService
from agenda.models import Schedule, TimeSlot
from agenda.selectors import ScheduleSelector
from agenda.services import ScheduleService
from audit.models import AuditLog
from base.exceptions import BusinessRuleViolationError, PermissionDeniedError, ValidationError
from classes.models import Class
from rooms.models import Room
from teachers.models import Subject, Teacher


def _time_slot(
    user,
    number=1,
    start=dt.time(8),
    end=dt.time(9),
    shift=TimeSlot.Shift.MORNING,
):
    return TimeSlot.objects.create(
        slot_number=number,
        shift=shift,
        start_time=start,
        end_time=end,
        created_by=user,
        updated_by=user,
    )


def _teacher(user, registration="GRADE-001"):
    from core.models import CustomUser

    profile_user = CustomUser.objects.create_user(
        email=f"{registration.lower()}@test.local", password="Senha123", first_name="Docente"
    )
    return Teacher.objects.create(
        user=profile_user, registration_number=registration, created_by=user, updated_by=user
    )


def _subject(user, code="MAT"):
    return Subject.objects.create(
        name=f"Disciplina {code}", code=code, created_by=user, updated_by=user
    )


def _class(user, suffix="A", shift=Class.Shift.MORNING):
    return Class.objects.create(
        name=f"1º A {suffix}",
        grade=Class.Grade.ELEMENTARY_1,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=2026,
        shift=shift,
        created_by=user,
        updated_by=user,
    )


def _room(user, code="S1"):
    return Room.objects.create(
        name=f"Sala {code}", code=code, capacity=30, created_by=user, updated_by=user
    )


def _schedule_data(class_obj, teacher, subject, time_slot, **overrides):
    return {
        "class_obj_id": class_obj.pk,
        "teacher_id": teacher.pk,
        "subject_id": subject.pk,
        "time_slot_id": time_slot.pk,
        "day_of_week": Schedule.Day.MON,
        "valid_from": dt.date(2026, 2, 2),
        **overrides,
    }


def _teacher_actor_with_schedule_write_access(user):
    from core.models import CustomUser, Role, RoleModuleAccess

    role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
    RoleModuleAccess.objects.update_or_create(
        role=role,
        module_key="schedule",
        defaults={"can_view": True, "can_create": True, "can_edit": True},
    )
    actor = CustomUser.objects.create_user(email="schedule-actor@test.local", password="Senha123")
    actor.role = role
    actor.is_superuser = False
    actor.save(update_fields=["role", "is_superuser"])
    teacher = Teacher.objects.create(
        user=actor, registration_number="SCHEDULE-ACTOR", created_by=user, updated_by=user
    )
    return actor, teacher


@pytest.mark.django_db
def test_create_time_slot_rejects_overlapping_common_period(user):
    ScheduleService(user=user).create_time_slot(
        {
            "slot_number": 1,
            "shift": TimeSlot.Shift.MORNING,
            "start_time": dt.time(8),
            "end_time": dt.time(9),
        }
    )

    with pytest.raises(ValidationError):
        ScheduleService(user=user).create_time_slot(
            {
                "slot_number": 2,
                "shift": TimeSlot.Shift.AFTERNOON,
                "start_time": dt.time(8, 30),
                "end_time": dt.time(9, 30),
            }
        )


@pytest.mark.django_db
def test_create_and_update_time_slot_require_valid_shift_and_audit_it(user):
    service = ScheduleService(user=user)

    with pytest.raises(ValidationError) as missing_error:
        service.create_time_slot(
            {"slot_number": 1, "start_time": dt.time(7), "end_time": dt.time(8)}
        )
    assert "shift" in missing_error.value.errors

    with pytest.raises(ValidationError) as invalid_error:
        service.create_time_slot(
            {
                "slot_number": 1,
                "shift": "FULL",
                "start_time": dt.time(7),
                "end_time": dt.time(8),
            }
        )
    assert "shift" in invalid_error.value.errors

    slot = service.create_time_slot(
        {
            "slot_number": 1,
            "shift": TimeSlot.Shift.MORNING,
            "start_time": dt.time(7),
            "end_time": dt.time(8),
        }
    )
    created_audit = AuditLog.objects.get(
        model_name="TimeSlot", object_id=str(slot.pk), operation="INSERT"
    )
    assert created_audit.new_values == {
        "slot_number": 1,
        "shift": TimeSlot.Shift.MORNING,
        "start_time": "07:00:00",
        "end_time": "08:00:00",
    }

    updated = service.update_time_slot(
        slot.pk,
        {
            "slot_number": 2,
            "shift": TimeSlot.Shift.AFTERNOON,
            "start_time": dt.time(13),
            "end_time": dt.time(14),
            "version": slot.version,
        },
    )
    updated_audit = AuditLog.objects.get(
        model_name="TimeSlot", object_id=str(slot.pk), operation="UPDATE"
    )
    assert updated.shift == TimeSlot.Shift.AFTERNOON
    assert updated_audit.old_values["shift"] == TimeSlot.Shift.MORNING
    assert updated_audit.new_values == {
        "slot_number": 2,
        "shift": TimeSlot.Shift.AFTERNOON,
        "start_time": "13:00:00",
        "end_time": "14:00:00",
    }

    with pytest.raises(BusinessRuleViolationError):
        service.update_time_slot(
            slot.pk,
            {
                "slot_number": 3,
                "shift": TimeSlot.Shift.NIGHT,
                "start_time": dt.time(18),
                "end_time": dt.time(19),
                "version": 0,
            },
        )


@pytest.mark.django_db
def test_update_time_slot_rejects_changes_when_any_schedule_uses_it(user):
    class_obj = _class(user)
    teacher = _teacher(user)
    subject = _subject(user)
    teacher.subjects.add(subject)
    slot = _time_slot(user)
    service = ScheduleService(user=user)
    schedule = service.create_schedule(_schedule_data(class_obj, teacher, subject, slot))
    schedule.soft_delete(user=user)
    audit_count = AuditLog.objects.count()

    with pytest.raises(BusinessRuleViolationError):
        service.update_time_slot(
            slot.pk,
            {
                "slot_number": 1,
                "shift": TimeSlot.Shift.AFTERNOON,
                "start_time": dt.time(13),
                "end_time": dt.time(14),
                "version": slot.version,
            },
        )

    slot.refresh_from_db()
    assert slot.shift == TimeSlot.Shift.MORNING
    assert AuditLog.objects.count() == audit_count


@pytest.mark.django_db
def test_get_class_matrix_filters_all_class_shifts_and_orders_chronologically(user):
    _time_slot(
        user,
        number=9,
        start=dt.time(13),
        end=dt.time(14),
        shift=TimeSlot.Shift.AFTERNOON,
    )
    _time_slot(
        user,
        number=3,
        start=dt.time(7),
        end=dt.time(8),
        shift=TimeSlot.Shift.MORNING,
    )
    _time_slot(
        user,
        number=1,
        start=dt.time(19),
        end=dt.time(20),
        shift=TimeSlot.Shift.NIGHT,
    )
    classes = {
        shift: _class(user, suffix=shift, shift=shift)
        for shift in (
            Class.Shift.MORNING,
            Class.Shift.AFTERNOON,
            Class.Shift.NIGHT,
            Class.Shift.FULL,
        )
    }

    matrix_shifts = {
        shift: [
            row.time_slot.shift
            for row in ScheduleSelector().get_class_matrix(class_obj.pk, dt.date(2026, 2, 2))
        ]
        for shift, class_obj in classes.items()
    }

    assert matrix_shifts == {
        Class.Shift.MORNING: [TimeSlot.Shift.MORNING],
        Class.Shift.AFTERNOON: [TimeSlot.Shift.AFTERNOON],
        Class.Shift.NIGHT: [TimeSlot.Shift.NIGHT],
        Class.Shift.FULL: [TimeSlot.Shift.MORNING, TimeSlot.Shift.AFTERNOON],
    }


@pytest.mark.django_db
def test_create_schedule_rejects_incompatible_slot_without_writing_or_auditing(user):
    class_obj = _class(user)
    teacher = _teacher(user)
    subject = _subject(user)
    teacher.subjects.add(subject)
    incompatible_slot = _time_slot(
        user,
        start=dt.time(13),
        end=dt.time(14),
        shift=TimeSlot.Shift.AFTERNOON,
    )
    audit_count = AuditLog.objects.count()

    with pytest.raises(BusinessRuleViolationError):
        ScheduleService(user=user).create_schedule(
            _schedule_data(class_obj, teacher, subject, incompatible_slot)
        )

    assert Schedule.objects.count() == 0
    assert AuditLog.objects.count() == audit_count


@pytest.mark.django_db
def test_create_schedule_requires_teacher_subject_and_audits(user):
    class_obj = _class(user)
    teacher = _teacher(user)
    subject = _subject(user)
    slot = _time_slot(user)

    with pytest.raises(BusinessRuleViolationError):
        ScheduleService(user=user).create_schedule(
            _schedule_data(class_obj, teacher, subject, slot)
        )

    teacher.subjects.add(subject)
    schedule = ScheduleService(user=user).create_schedule(
        _schedule_data(class_obj, teacher, subject, slot)
    )

    assert AuditLog.objects.filter(model_name="Schedule", object_id=str(schedule.pk)).exists()


@pytest.mark.django_db
def test_create_schedule_rejects_class_teacher_and_room_conflicts(user):
    first_class = _class(user)
    second_class = _class(user, "B")
    teacher = _teacher(user)
    subject = _subject(user)
    teacher.subjects.add(subject)
    slot = _time_slot(user)
    room = _room(user)
    service = ScheduleService(user=user)
    service.create_schedule(_schedule_data(first_class, teacher, subject, slot, room_id=room.pk))

    with pytest.raises(BusinessRuleViolationError):
        service.create_schedule(
            _schedule_data(first_class, teacher, subject, slot, room_id=room.pk)
        )
    with pytest.raises(BusinessRuleViolationError):
        service.create_schedule(_schedule_data(second_class, teacher, subject, slot))

    other_teacher = _teacher(user, "GRADE-002")
    other_teacher.subjects.add(subject)
    with pytest.raises(BusinessRuleViolationError):
        service.create_schedule(
            _schedule_data(second_class, other_teacher, subject, slot, room_id=room.pk)
        )


@pytest.mark.django_db
def test_schedule_valid_until_covers_full_week_for_activities(user):
    class_obj = _class(user)
    teacher = _teacher(user)
    subject = _subject(user)
    teacher.subjects.add(subject)
    slot = _time_slot(user)
    ScheduleService(user=user).create_schedule(
        _schedule_data(class_obj, teacher, subject, slot, valid_until=dt.date(2026, 2, 4))
    )

    schedule = Schedule.objects.get(class_obj=class_obj)
    assert schedule.valid_until == dt.date(2026, 2, 8)

    rows = ScheduleSelector().get_class_matrix(class_obj.pk, dt.date(2026, 2, 6))

    assert len(rows) == 1
    assert [cell.day_of_week for cell in rows[0].cells] == list(Schedule.Day.values)
    assert rows[0].cells[0].schedule is not None
    assert (
        ScheduleSelector().get_class_matrix(class_obj.pk, dt.date(2026, 2, 9))[0].cells[0].schedule
        is None
    )
    activity = ActivityService(user=user).create_activity(
        {
            "class_obj_id": class_obj.pk,
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "title": "Atividade da sexta",
            "due_date": dt.date(2026, 2, 6),
            "max_score": 10,
        }
    )
    assert activity.pk is not None
    with pytest.raises(ValidationError):
        ActivityService(user=user).create_activity(
            {
                "class_obj_id": class_obj.pk,
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "title": "Atividade fora da vigência",
                "due_date": dt.date(2026, 2, 9),
                "max_score": 10,
            }
        )


@pytest.mark.django_db
def test_create_successor_ends_predecessor_and_rejects_stale_version(user):
    class_obj = _class(user)
    teacher = _teacher(user)
    subject = _subject(user)
    teacher.subjects.add(subject)
    slot = _time_slot(user)
    service = ScheduleService(user=user)
    schedule = service.create_schedule(_schedule_data(class_obj, teacher, subject, slot))

    successor = service.create_schedule_successor(
        schedule.pk,
        _schedule_data(
            class_obj,
            teacher,
            subject,
            slot,
            valid_from=dt.date(2026, 3, 2),
            version=schedule.version,
        ),
    )
    schedule.refresh_from_db()

    assert schedule.valid_until == dt.date(2026, 3, 1)
    assert successor.valid_from == dt.date(2026, 3, 2)
    with pytest.raises(BusinessRuleViolationError):
        service.end_schedule(schedule.pk, {"valid_until": dt.date(2026, 2, 20), "version": 0})


@pytest.mark.django_db
def test_schedule_commands_normalize_dates_to_week_boundaries(user):
    class_obj = _class(user)
    teacher = _teacher(user)
    subject = _subject(user)
    teacher.subjects.add(subject)
    slot = _time_slot(user)
    service = ScheduleService(user=user)

    schedule = service.create_schedule(
        _schedule_data(
            class_obj,
            teacher,
            subject,
            slot,
            valid_from=dt.date(2026, 2, 5),
            valid_until=dt.date(2026, 2, 25),
        )
    )
    assert schedule.valid_from == dt.date(2026, 2, 2)
    assert schedule.valid_until == dt.date(2026, 3, 1)

    successor = service.create_schedule_successor(
        schedule.pk,
        _schedule_data(
            class_obj,
            teacher,
            subject,
            slot,
            valid_from=dt.date(2026, 2, 19),
            version=schedule.version,
        ),
    )
    schedule.refresh_from_db()
    assert schedule.valid_until == dt.date(2026, 2, 15)
    assert successor.valid_from == dt.date(2026, 2, 16)

    ended = service.end_schedule(
        successor.pk,
        {"valid_until": dt.date(2026, 2, 25), "version": successor.version},
    )
    assert ended.valid_until == dt.date(2026, 2, 22)


@pytest.mark.django_db
def test_copy_schedule_day_normalizes_reference_to_monday(user):
    class_obj = _class(user)
    teacher = _teacher(user)
    subject = _subject(user)
    teacher.subjects.add(subject)
    slot = _time_slot(user)
    service = ScheduleService(user=user)
    service.create_schedule(_schedule_data(class_obj, teacher, subject, slot))

    copied = service.copy_schedule_day(
        class_obj.pk,
        {
            "source_day": Schedule.Day.MON,
            "target_day": Schedule.Day.TUE,
            "as_of": dt.date(2026, 2, 7),
        },
    )

    assert copied[0].valid_from == dt.date(2026, 2, 2)


@pytest.mark.django_db
def test_copy_day_is_atomic_when_target_conflicts(user):
    class_obj = _class(user)
    teacher = _teacher(user)
    subject = _subject(user)
    teacher.subjects.add(subject)
    slot = _time_slot(user)
    service = ScheduleService(user=user)
    service.create_schedule(_schedule_data(class_obj, teacher, subject, slot))
    other_teacher = _teacher(user, "GRADE-003")
    other_teacher.subjects.add(subject)
    service.create_schedule(
        _schedule_data(class_obj, other_teacher, subject, slot, day_of_week=Schedule.Day.TUE)
    )

    with pytest.raises(BusinessRuleViolationError):
        service.copy_schedule_day(
            class_obj.pk,
            {
                "source_day": Schedule.Day.MON,
                "target_day": Schedule.Day.TUE,
                "as_of": dt.date(2026, 2, 2),
            },
        )

    assert Schedule.objects.filter(class_obj=class_obj, day_of_week=Schedule.Day.TUE).count() == 1


@pytest.mark.django_db
def test_create_schedule_denies_teacher_without_create_permission(user):
    from core.models import Role

    role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
    user.role = role
    user.is_superuser = False
    user.save(update_fields=["role", "is_superuser"])

    with pytest.raises(PermissionDeniedError):
        ScheduleService(user=user).create_schedule({})


@pytest.mark.django_db
def test_teacher_schedule_write_does_not_grant_period_catalog_commands(user):
    actor, _teacher_profile = _teacher_actor_with_schedule_write_access(user)
    slot = _time_slot(user)
    audits_before = AuditLog.objects.filter(model_name="TimeSlot").count()

    with pytest.raises(PermissionDeniedError):
        ScheduleService(user=actor).create_time_slot(
            {
                "slot_number": 2,
                "shift": TimeSlot.Shift.MORNING,
                "start_time": dt.time(9),
                "end_time": dt.time(10),
            }
        )
    with pytest.raises(PermissionDeniedError):
        ScheduleService(user=actor).update_time_slot(
            slot.pk,
            {
                "slot_number": 1,
                "shift": TimeSlot.Shift.AFTERNOON,
                "start_time": dt.time(13),
                "end_time": dt.time(14),
                "version": slot.version,
            },
        )

    slot.refresh_from_db()
    assert TimeSlot.objects.count() == 1
    assert slot.shift == TimeSlot.Shift.MORNING
    assert AuditLog.objects.filter(model_name="TimeSlot").count() == audits_before


@pytest.mark.django_db
def test_create_schedule_denies_teacher_with_write_permission_outside_class_scope(user):
    actor, actor_teacher = _teacher_actor_with_schedule_write_access(user)
    class_obj = _class(user)
    subject = _subject(user)
    actor_teacher.subjects.add(subject)
    slot = _time_slot(user)

    with pytest.raises(PermissionDeniedError):
        ScheduleService(user=actor).create_schedule(
            _schedule_data(class_obj, actor_teacher, subject, slot)
        )


@pytest.mark.django_db
def test_teacher_with_schedule_write_can_create_and_edit_within_class_scope(user):
    actor, actor_teacher = _teacher_actor_with_schedule_write_access(user)
    class_obj = _class(user)
    class_obj.class_teacher = actor_teacher
    class_obj.save(update_fields=["class_teacher"])
    subject = _subject(user)
    actor_teacher.subjects.add(subject)
    slot = _time_slot(user)
    service = ScheduleService(user=actor)

    current = service.create_schedule(_schedule_data(class_obj, actor_teacher, subject, slot))
    successor = service.create_schedule_successor(
        current.pk,
        _schedule_data(
            class_obj,
            actor_teacher,
            subject,
            slot,
            valid_from=dt.date(2026, 3, 2),
            version=current.version,
        ),
    )

    current.refresh_from_db()
    assert current.valid_until == dt.date(2026, 3, 1)
    assert successor.valid_from == dt.date(2026, 3, 2)


@pytest.mark.django_db
def test_soft_deleted_schedule_revokes_teacher_class_scope(user):
    from core.access_selectors import ObjectAccessSelector

    actor, actor_teacher = _teacher_actor_with_schedule_write_access(user)
    class_obj = _class(user)
    subject = _subject(user)
    actor_teacher.subjects.add(subject)
    slot = _time_slot(user)
    schedule = ScheduleService(user=user).create_schedule(
        _schedule_data(class_obj, actor_teacher, subject, slot)
    )

    assert ObjectAccessSelector.teacher_can_access_class(actor.pk, class_obj.pk) is True
    as_of = dt.date(2026, 2, 2)
    assert (
        ScheduleSelector.teacher_can_access_class(class_obj.pk, user_id=actor.pk, as_of=as_of)
        is True
    )

    schedule.soft_delete(user=user)

    assert ObjectAccessSelector.teacher_can_access_class(actor.pk, class_obj.pk) is False
    assert (
        ScheduleSelector.teacher_can_access_class(class_obj.pk, user_id=actor.pk, as_of=as_of)
        is False
    )
    with pytest.raises(PermissionDeniedError):
        ScheduleSelector().get_class_for_matrix(
            class_obj.pk,
            user_id=actor.pk,
            role_name="TEACHER",
            as_of=as_of,
        )


@pytest.mark.django_db
def test_expired_schedule_revokes_teacher_class_scope_for_selected_week(user):
    actor, actor_teacher = _teacher_actor_with_schedule_write_access(user)
    class_obj = _class(user)
    subject = _subject(user)
    actor_teacher.subjects.add(subject)
    slot = _time_slot(user)
    ScheduleService(user=user).create_schedule(
        _schedule_data(
            class_obj,
            actor_teacher,
            subject,
            slot,
            valid_until=dt.date(2026, 2, 8),
        )
    )

    assert ScheduleSelector.teacher_can_access_class(
        class_obj.pk,
        user_id=actor.pk,
        as_of=dt.date(2026, 2, 2),
    )
    assert not ScheduleSelector.teacher_can_access_class(
        class_obj.pk,
        user_id=actor.pk,
        as_of=dt.date(2026, 2, 9),
    )
    with pytest.raises(PermissionDeniedError):
        ScheduleSelector().get_class_for_matrix(
            class_obj.pk,
            user_id=actor.pk,
            role_name="TEACHER",
            as_of=dt.date(2026, 2, 9),
        )


@pytest.mark.django_db
def test_create_successor_denies_teacher_with_write_permission_outside_class_scope(user):
    actor, _actor_teacher = _teacher_actor_with_schedule_write_access(user)
    class_obj = _class(user)
    teacher = _teacher(user)
    subject = _subject(user)
    teacher.subjects.add(subject)
    slot = _time_slot(user)
    schedule = ScheduleService(user=user).create_schedule(
        _schedule_data(class_obj, teacher, subject, slot)
    )

    with pytest.raises(PermissionDeniedError):
        ScheduleService(user=actor).create_schedule_successor(
            schedule.pk,
            _schedule_data(
                class_obj,
                teacher,
                subject,
                slot,
                valid_from=dt.date(2026, 3, 2),
                version=schedule.version,
            ),
        )


@pytest.mark.django_db
def test_end_schedule_denies_teacher_with_write_permission_outside_class_scope(user):
    actor, _actor_teacher = _teacher_actor_with_schedule_write_access(user)
    class_obj = _class(user)
    teacher = _teacher(user)
    subject = _subject(user)
    teacher.subjects.add(subject)
    slot = _time_slot(user)
    schedule = ScheduleService(user=user).create_schedule(
        _schedule_data(class_obj, teacher, subject, slot)
    )

    with pytest.raises(PermissionDeniedError):
        ScheduleService(user=actor).end_schedule(
            schedule.pk,
            {"valid_until": dt.date(2026, 2, 2), "version": schedule.version},
        )


@pytest.mark.django_db
def test_copy_schedule_day_denies_teacher_with_write_permission_outside_class_scope(user):
    actor, _actor_teacher = _teacher_actor_with_schedule_write_access(user)
    class_obj = _class(user)
    teacher = _teacher(user)
    subject = _subject(user)
    teacher.subjects.add(subject)
    slot = _time_slot(user)
    ScheduleService(user=user).create_schedule(_schedule_data(class_obj, teacher, subject, slot))

    with pytest.raises(PermissionDeniedError):
        ScheduleService(user=actor).copy_schedule_day(
            class_obj.pk,
            {
                "source_day": Schedule.Day.MON,
                "target_day": Schedule.Day.TUE,
                "as_of": dt.date(2026, 2, 2),
            },
        )
