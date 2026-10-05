"""Testes HTTP da matriz de horários."""

import datetime as dt
import json

import pytest
from django.contrib.messages import get_messages
from django.templatetags.static import static
from django.urls import reverse

from agenda.models import Schedule, TimeSlot
from agenda.services import ScheduleService
from audit.models import AuditLog
from classes.models import Class
from teachers.models import Subject, Teacher


def _class(user, *, name="1º A", academic_year=2026):
    return Class.objects.create(
        name=name,
        grade=Class.Grade.ELEMENTARY_1,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=academic_year,
        shift=Class.Shift.MORNING,
        created_by=user,
        updated_by=user,
    )


def _teacher_with_subject(user):
    from core.models import CustomUser

    target = CustomUser.objects.create_user(email="docente@grade.test", password="Senha123")
    teacher = Teacher.objects.create(
        user=target, registration_number="GRADE-001", created_by=user, updated_by=user
    )
    subject = Subject.objects.create(
        name="Matemática", code="MAT", created_by=user, updated_by=user
    )
    teacher.subjects.add(subject)
    return teacher, subject


def _teacher_actor(user):
    from core.models import CustomUser, Role, RoleModuleAccess

    role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
    RoleModuleAccess.objects.update_or_create(
        role=role,
        module_key="schedule",
        defaults={"can_view": True, "can_create": True, "can_edit": True},
    )
    actor = CustomUser.objects.create_user(email="professor.grade@test", password="Senha123")
    actor.role = role
    actor.is_superuser = False
    actor.save(update_fields=["role", "is_superuser"])
    teacher = Teacher.objects.create(
        user=actor, registration_number="GRADE-ACTOR", created_by=user, updated_by=user
    )
    return actor, teacher


@pytest.mark.django_db
def test_schedule_classes_list_renders_canonical_selection_and_htmx(client, user):
    client.force_login(user)
    class_obj = _class(user)
    url = reverse("schedule_classes_list")

    response = client.get(url)
    partial = client.get(f"{url}?q=1%C2%BA", HTTP_HX_REQUEST="true")
    boosted = client.get(
        url,
        HTTP_HX_REQUEST="true",
        HTTP_HX_BOOSTED="true",
    )

    assert response.status_code == 200
    assert b"Lista de Grade Hor" in response.content
    assert reverse("schedule_weekly", args=[class_obj.pk]).encode() in response.content
    assert "Períodos".encode() in response.content
    assert partial.status_code == 200
    assert b"schedule-classes-table" in partial.content
    assert b"page-header" not in partial.content
    assert boosted.status_code == 200
    assert b"<!DOCTYPE html>" in boosted.content
    assert b'id="app-main"' in boosted.content


@pytest.mark.django_db
def test_schedule_classes_list_filters_orders_and_paginates_with_htmx(client, user):
    client.force_login(user)
    for index in range(21):
        _class(user, name=f"Turma {index:02d}", academic_year=2020 + index)

    response = client.get(
        reverse("schedule_classes_list") + "?q=Turma&sort=name&page=2",
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Turma 20" in response.content
    assert b"1 / 2" not in response.content
    assert b"2 / 2" in response.content


@pytest.mark.django_db
def test_schedule_classes_list_limits_teacher_to_owned_and_scheduled_classes(client, user):
    actor, teacher = _teacher_actor(user)
    owned_class = _class(user)
    owned_class.name = "Titular"
    owned_class.class_teacher = teacher
    owned_class.save(update_fields=["name", "class_teacher"])
    scheduled_class = _class(user)
    scheduled_class.name = "Com horário"
    scheduled_class.save(update_fields=["name"])
    other_class = _class(user)
    other_class.name = "Fora do escopo"
    other_class.save(update_fields=["name"])
    subject = Subject.objects.create(name="História", code="HIS", created_by=user, updated_by=user)
    teacher.subjects.add(subject)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    schedule = ScheduleService(user=user).create_schedule(
        {
            "class_obj_id": scheduled_class.pk,
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "time_slot_id": slot.pk,
            "day_of_week": Schedule.Day.MON,
            "valid_from": dt.date(2026, 2, 1),
        }
    )
    client.force_login(actor)

    response = client.get(reverse("schedule_classes_list"))

    assert response.status_code == 200
    assert b"Titular" in response.content
    assert "Com horário".encode() in response.content
    assert b"Fora do escopo" not in response.content

    schedule.soft_delete(user=user)
    revoked_response = client.get(reverse("schedule_classes_list"))

    assert "Com horário".encode() not in revoked_response.content


@pytest.mark.django_db
def test_schedule_matrix_renders_monday_to_friday_and_htmx_workspace(client, user):
    client.force_login(user)
    class_obj = _class(user)
    TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    url = reverse("schedule_weekly", args=[class_obj.pk]) + "?as_of=2026-02-02"

    response = client.get(url)
    partial = client.get(url, HTTP_HX_REQUEST="true")
    boosted = client.get(url, HTTP_HX_REQUEST="true", HTTP_HX_BOOSTED="true")

    assert response.status_code == 200
    assert b"Segunda (02/02)" in response.content
    assert b"Sexta (06/02)" in response.content
    assert b"S\xc3\xa1bado" not in response.content
    assert b'id="app-modal-root"' in response.content
    assert b'id="schedule-cell-modal"' in response.content
    assert b'id="schedule-copy-modal"' in response.content
    assert static("js/sm-schedule-modals.js").encode() in response.content
    assert b"data-sm-schedule-cell-modal" in response.content
    assert b"data-sm-schedule-copy-modal" in response.content
    assert b"scheduleModalState" not in response.content
    assert b"config.elt" not in response.content
    assert b"clearPendingScheduleModalRequest" not in response.content
    assert b'data-bs-target="#schedule-cell-modal"' not in response.content
    assert b"sm-schedule-cell-form" not in response.content
    assert b'id="app-history-root"' in response.content
    assert response.content.index(b'id="app-main"') < response.content.index(b'id="app-modal-root"')
    assert response.content.index(b'id="app-modal-root"') < response.content.index(
        b'id="schedule-cell-modal"'
    )
    assert partial.status_code == 200
    assert b"schedule-matrix-workspace" in partial.content
    assert b"page-header" not in partial.content
    assert boosted.status_code == 200
    assert b"<!DOCTYPE html>" in boosted.content
    assert b'id="app-main"' in boosted.content
    assert b'id="app-modal-root"' in boosted.content


@pytest.mark.django_db
def test_schedule_matrix_week_navigation_preserves_as_of_and_replaces_workspace(client, user):
    client.force_login(user)
    class_obj = _class(user)
    url = reverse("schedule_weekly", args=[class_obj.pk]) + "?as_of=2026-02-02"

    response = client.get(url)

    assert response.status_code == 200
    assert b'name="as_of"' not in response.content
    assert b">Carregar<" not in response.content
    assert b">Seg<" not in response.content and b">S\xc3\xa1b<" not in response.content
    assert b"Segunda (02/02)" in response.content and b"Sexta (06/02)" in response.content
    assert (
        f'href="{reverse("schedule_weekly", args=[class_obj.pk])}?as_of=2026-01-26"'.encode()
        in response.content
    )
    assert b'hx-target="#schedule-matrix-workspace"' in response.content
    assert b'hx-swap="outerHTML"' in response.content
    assert (
        f'hx-push-url="{reverse("schedule_weekly", args=[class_obj.pk])}?as_of=2026-01-26"'.encode()
        in response.content
    )
    assert (
        f'hx-push-url="{reverse("schedule_weekly", args=[class_obj.pk])}?as_of=2026-02-09"'.encode()
        in response.content
    )


@pytest.mark.django_db
def test_schedule_matrix_redirects_non_monday_references_to_canonical_url(client, user):
    client.force_login(user)
    class_obj = _class(user)
    url = reverse("schedule_weekly", args=[class_obj.pk])

    response = client.get(f"{url}?as_of=2026-02-07")
    htmx_response = client.get(f"{url}?as_of=2026-02-08", HTTP_HX_REQUEST="true")

    assert response.status_code == 302
    assert response["Location"] == f"{url}?as_of=2026-02-02"
    assert htmx_response.status_code == 204
    assert htmx_response["HX-Redirect"] == f"{url}?as_of=2026-02-02"


@pytest.mark.django_db
def test_time_slots_list_normalizes_invalid_page_query(client, user):
    client.force_login(user)

    response = client.get(reverse("time_slots_list") + "?page=abc")

    assert response.status_code == 200


@pytest.mark.django_db
def test_time_slots_list_returns_only_table_and_pagination_for_htmx(client, user):
    client.force_login(user)
    start = dt.datetime.combine(dt.date(2026, 1, 1), dt.time(7))
    for number in range(21):
        slot_start = start + dt.timedelta(minutes=20 * number)
        TimeSlot.objects.create(
            slot_number=number + 1,
            shift=TimeSlot.Shift.MORNING,
            start_time=slot_start.time(),
            end_time=(slot_start + dt.timedelta(minutes=20)).time(),
            created_by=user,
            updated_by=user,
        )

    url = reverse("time_slots_list")
    response = client.get(url)
    partial = client.get(f"{url}?page=2", HTTP_HX_REQUEST="true")

    assert response.status_code == partial.status_code == 200
    assert b"<!DOCTYPE html>" in response.content
    assert b"Lista de Per" in response.content
    assert b"<!DOCTYPE html>" not in partial.content
    assert b'id="time-slots-table"' not in partial.content
    assert b"21 / 2" not in partial.content
    assert b"2 / 2" in partial.content
    assert b'hx-target="#time-slots-table"' in partial.content


@pytest.mark.django_db
def test_time_slot_form_requires_shift_and_list_displays_it(client, user):
    client.force_login(user)
    create_url = reverse("time_slot_create")

    form_response = client.get(create_url)
    invalid_response = client.post(
        create_url,
        {"slot_number": 1, "start_time": "13:00", "end_time": "14:00"},
    )
    created_response = client.post(
        create_url,
        {
            "slot_number": 1,
            "shift": TimeSlot.Shift.AFTERNOON,
            "start_time": "13:00",
            "end_time": "14:00",
        },
    )
    list_response = client.get(reverse("time_slots_list"))

    assert form_response.status_code == 200
    assert b'name="shift"' in form_response.content
    assert invalid_response.status_code == 200
    assert b"Este campo" in invalid_response.content
    assert created_response.status_code == 302
    assert b"Vespertino" in list_response.content


@pytest.mark.django_db
def test_schedule_matrix_empty_state_identifies_class_shift(client, user):
    client.force_login(user)
    class_obj = _class(user)
    class_obj.shift = Class.Shift.NIGHT
    class_obj.save(update_fields=["shift"])
    TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )

    response = client.get(reverse("schedule_weekly", args=[class_obj.pk]) + "?as_of=2026-02-02")

    assert response.status_code == 200
    assert "Não existem períodos cadastrados para o turno Noturno".encode() in response.content


@pytest.mark.django_db
def test_schedule_cell_create_returns_not_found_for_incompatible_slot_on_get_and_post(client, user):
    client.force_login(user)
    class_obj = _class(user)
    teacher, subject = _teacher_with_subject(user)
    incompatible_slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.AFTERNOON,
        start_time=dt.time(13),
        end_time=dt.time(14),
        created_by=user,
        updated_by=user,
    )
    url = reverse(
        "schedule_cell_create",
        args=[class_obj.pk, Schedule.Day.MON, incompatible_slot.pk],
    )
    audit_count = AuditLog.objects.count()

    get_response = client.get(f"{url}?as_of=2026-02-02")
    post_response = client.post(
        f"{url}?as_of=2026-02-02",
        {
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "room_id": "",
            "valid_from": "2026-02-02",
        },
    )

    assert get_response.status_code == post_response.status_code == 404
    assert Schedule.objects.count() == 0
    assert AuditLog.objects.count() == audit_count


@pytest.mark.django_db
def test_schedule_cell_create_post_replaces_only_cell_oob_and_closes_modal(client, user):
    client.force_login(user)
    class_obj = _class(user)
    teacher, subject = _teacher_with_subject(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    url = reverse("schedule_cell_create", args=[class_obj.pk, Schedule.Day.MON, slot.pk])

    response = client.post(
        f"{url}?as_of=2026-02-02",
        {
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "room_id": "",
            "valid_from": "2026-02-02",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"schedule-cell-MON" in response.content
    assert b'hx-swap-oob="outerHTML"' in response.content
    assert b"data-sm-close-schedule-modal" not in response.content
    assert json.loads(response["HX-Trigger-After-Settle"]) == {
        "schedule-cell-saved": {
            "returnFocus": f"schedule-cell-MON-{slot.pk}-edit",
        }
    }
    assert list(get_messages(response.wsgi_request)) == []


@pytest.mark.django_db
def test_schedule_cell_create_htmx_keeps_future_cell_empty_at_as_of_date(client, user):
    client.force_login(user)
    class_obj = _class(user)
    teacher, subject = _teacher_with_subject(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    url = reverse("schedule_cell_create", args=[class_obj.pk, Schedule.Day.MON, slot.pk])

    response = client.post(
        f"{url}?as_of=2026-02-02",
        {
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "room_id": "",
            "valid_from": "2026-03-02",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Adicionar" in response.content
    assert b"Matem\xc3\xa1tica" not in response.content
    assert b'hx-swap-oob="outerHTML"' in response.content


@pytest.mark.django_db
def test_schedule_cell_create_htmx_validation_stays_inside_modal(client, user):
    client.force_login(user)
    class_obj = _class(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )

    response = client.post(
        reverse("schedule_cell_create", args=[class_obj.pk, Schedule.Day.MON, slot.pk])
        + "?as_of=2026-02-02",
        {"teacher_id": ""},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b'id="schedule-cell-modal-body"' in response.content
    assert b'aria-live="polite"' in response.content
    assert b"Este campo" in response.content
    assert b'hx-target="#schedule-cell-modal-body"' in response.content
    assert b"data-sm-close-schedule-modal" not in response.content


@pytest.mark.django_db
def test_schedule_cell_edit_htmx_keeps_predecessor_visible_before_future_successor(client, user):
    client.force_login(user)
    class_obj = _class(user)
    teacher, subject = _teacher_with_subject(user)
    future_subject = Subject.objects.create(
        name="Ciências", code="CIE", created_by=user, updated_by=user
    )
    teacher.subjects.add(future_subject)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    schedule = ScheduleService(user=user).create_schedule(
        {
            "class_obj_id": class_obj.pk,
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "time_slot_id": slot.pk,
            "day_of_week": Schedule.Day.MON,
            "valid_from": dt.date(2026, 2, 1),
        }
    )
    url = reverse("schedule_cell_edit", args=[class_obj.pk, schedule.pk])

    response = client.post(
        f"{url}?as_of=2026-02-02",
        {
            "teacher_id": teacher.pk,
            "subject_id": future_subject.pk,
            "room_id": "",
            "valid_from": "2026-03-02",
            "version": schedule.version,
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Matem\xc3\xa1tica" in response.content
    assert b"Ci\xc3\xaancias" not in response.content


@pytest.mark.django_db
def test_schedule_cell_end_and_copy_return_htmx_canonical_fragments(client, user):
    client.force_login(user)
    class_obj = _class(user)
    teacher, subject = _teacher_with_subject(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    schedule = ScheduleService(user=user).create_schedule(
        {
            "class_obj_id": class_obj.pk,
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "time_slot_id": slot.pk,
            "day_of_week": Schedule.Day.MON,
            "valid_from": dt.date(2026, 2, 1),
        }
    )

    end_response = client.post(
        reverse("schedule_cell_end", args=[class_obj.pk, schedule.pk]) + "?as_of=2026-02-02",
        {"valid_until": "2026-02-09", "version": schedule.version},
        HTTP_HX_REQUEST="true",
    )
    copy_response = client.post(
        reverse("schedule_day_copy", args=[class_obj.pk]) + "?as_of=2026-02-02",
        {"source_day": Schedule.Day.MON, "target_day": Schedule.Day.TUE, "as_of": "2026-02-06"},
        HTTP_HX_REQUEST="true",
    )

    assert end_response.status_code == 200
    assert b"Matem\xc3\xa1tica" in end_response.content
    assert b"data-sm-close-schedule-modal" not in end_response.content
    assert "HX-Trigger-After-Settle" in end_response
    assert copy_response.status_code == 200
    assert b"schedule-matrix-workspace" in copy_response.content
    assert b'hx-swap-oob="outerHTML"' in copy_response.content
    assert json.loads(copy_response["HX-Trigger-After-Settle"]) == {
        "schedule-day-copied": {"returnFocus": "schedule-copy-day-trigger"}
    }
    assert (
        copy_response["HX-Push-Url"]
        == reverse("schedule_weekly", args=[class_obj.pk]) + "?as_of=2026-02-02"
    )
    assert Schedule.objects.filter(class_obj=class_obj, day_of_week=Schedule.Day.TUE).exists()


@pytest.mark.django_db
def test_schedule_cell_create_requires_schedule_create_permission(client, user):
    from core.models import Role

    role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
    user.role = role
    user.is_superuser = False
    user.save(update_fields=["role", "is_superuser"])
    client.force_login(user)
    class_obj = _class(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )

    response = client.get(
        reverse("schedule_cell_create", args=[class_obj.pk, Schedule.Day.MON, slot.pk])
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_time_slot_routes_use_view_create_and_edit_permissions(client, user):
    from core.models import Role, RoleModuleAccess

    role = Role.objects.get(name=Role.Name.COORDINATOR)
    RoleModuleAccess.objects.update_or_create(
        role=role,
        module_key="schedule_configuration",
        defaults={"can_view": True, "can_create": False, "can_edit": True},
    )
    user.role = role
    user.is_superuser = False
    user.save(update_fields=["role", "is_superuser"])
    client.force_login(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )

    list_response = client.get(reverse("time_slots_list"))
    create_response = client.get(reverse("time_slot_create"))
    edit_response = client.get(reverse("time_slot_edit", args=[slot.pk]))

    assert list_response.status_code == 200
    assert create_response.status_code == 403
    assert edit_response.status_code == 200


@pytest.mark.django_db
def test_time_slot_list_renders_plain_first_column_for_view_only_access(client, user):
    from core.models import Role, RoleModuleAccess

    role = Role.objects.get(name=Role.Name.COORDINATOR)
    RoleModuleAccess.objects.update_or_create(
        role=role,
        module_key="schedule_configuration",
        defaults={"can_view": True, "can_create": False, "can_edit": False},
    )
    user.role = role
    user.is_superuser = False
    user.save(update_fields=["role", "is_superuser"])
    client.force_login(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )

    response = client.get(reverse("time_slots_list"))

    assert response.status_code == 200
    assert b">1<" in response.content
    assert reverse("time_slot_edit", args=[slot.pk]).encode() not in response.content
    assert reverse("time_slot_create").encode() not in response.content


@pytest.mark.django_db
def test_teacher_schedule_access_does_not_expose_period_catalog_routes(client, user):
    actor, _teacher = _teacher_actor(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    client.force_login(actor)

    assert client.get(reverse("schedule_classes_list")).status_code == 200
    assert client.get(reverse("time_slots_list")).status_code == 403
    assert client.get(reverse("time_slot_create")).status_code == 403
    assert client.get(reverse("time_slot_edit", args=[slot.pk])).status_code == 403


@pytest.mark.django_db
def test_schedule_edit_and_end_routes_reject_incompatible_persisted_cell_on_get_and_post(
    client, user
):
    client.force_login(user)
    class_obj = _class(user)
    teacher, subject = _teacher_with_subject(user)
    incompatible_slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.AFTERNOON,
        start_time=dt.time(13),
        end_time=dt.time(14),
        created_by=user,
        updated_by=user,
    )
    schedule = Schedule.objects.create(
        class_obj=class_obj,
        teacher=teacher,
        subject=subject,
        time_slot=incompatible_slot,
        day_of_week=Schedule.Day.MON,
        valid_from=dt.date(2026, 2, 2),
        created_by=user,
        updated_by=user,
    )
    edit_url = reverse("schedule_cell_edit", args=[class_obj.pk, schedule.pk])
    end_url = reverse("schedule_cell_end", args=[class_obj.pk, schedule.pk])
    audit_count = AuditLog.objects.count()

    responses = (
        client.get(f"{edit_url}?as_of=2026-02-09"),
        client.post(
            f"{edit_url}?as_of=2026-02-09",
            {
                "teacher_id": teacher.pk,
                "subject_id": subject.pk,
                "room_id": "",
                "valid_from": "2026-02-09",
                "version": schedule.version,
            },
        ),
        client.get(f"{end_url}?as_of=2026-02-09"),
        client.post(
            f"{end_url}?as_of=2026-02-09",
            {"valid_until": "2026-02-09", "version": schedule.version},
        ),
    )

    assert all(response.status_code == 404 for response in responses)
    schedule.refresh_from_db()
    assert schedule.valid_until is None
    assert AuditLog.objects.count() == audit_count


@pytest.mark.django_db
def test_schedule_matrix_endpoints_deny_teacher_outside_class_scope(client, user):
    actor, actor_teacher = _teacher_actor(user)
    allowed_class = _class(user, name="Turma permitida")
    allowed_class.class_teacher = actor_teacher
    allowed_class.save(update_fields=["class_teacher"])
    forbidden_class = _class(user, name="Outra turma")
    assigned_teacher, subject = _teacher_with_subject(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    schedule = ScheduleService(user=user).create_schedule(
        {
            "class_obj_id": forbidden_class.pk,
            "teacher_id": assigned_teacher.pk,
            "subject_id": subject.pk,
            "time_slot_id": slot.pk,
            "day_of_week": Schedule.Day.MON,
            "valid_from": dt.date(2026, 2, 1),
        }
    )
    client.force_login(actor)

    urls = (
        reverse("schedule_weekly", args=[forbidden_class.pk]),
        reverse("schedule_cell_create", args=[forbidden_class.pk, Schedule.Day.MON, slot.pk]),
        reverse("schedule_cell_edit", args=[forbidden_class.pk, schedule.pk]),
        reverse("schedule_cell_end", args=[forbidden_class.pk, schedule.pk]),
        reverse("schedule_day_copy_form", args=[forbidden_class.pk]),
        reverse("schedule_day_copy", args=[forbidden_class.pk]),
    )

    assert all(client.get(url).status_code == 403 for url in urls)


@pytest.mark.django_db
def test_schedule_matrix_route_uses_selected_week_for_teacher_scope(client, user):
    actor, actor_teacher = _teacher_actor(user)
    class_obj = _class(user)
    subject = Subject.objects.create(
        name="Ciências",
        code="CIE",
        created_by=user,
        updated_by=user,
    )
    actor_teacher.subjects.add(subject)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    ScheduleService(user=user).create_schedule(
        {
            "class_obj_id": class_obj.pk,
            "teacher_id": actor_teacher.pk,
            "subject_id": subject.pk,
            "time_slot_id": slot.pk,
            "day_of_week": Schedule.Day.MON,
            "valid_from": dt.date(2026, 2, 2),
            "valid_until": dt.date(2026, 2, 8),
        }
    )
    url = reverse("schedule_weekly", args=[class_obj.pk])
    client.force_login(actor)

    assert client.get(f"{url}?as_of=2026-02-02").status_code == 200
    assert client.get(f"{url}?as_of=2026-02-09").status_code == 403


@pytest.mark.django_db
def test_schedule_cell_forms_use_real_actions_and_compact_modal(client, user):
    client.force_login(user)
    class_obj = _class(user)
    teacher, subject = _teacher_with_subject(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    schedule = ScheduleService(user=user).create_schedule(
        {
            "class_obj_id": class_obj.pk,
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "time_slot_id": slot.pk,
            "day_of_week": Schedule.Day.MON,
            "valid_from": dt.date(2026, 2, 1),
        }
    )
    as_of = "?as_of=2026-02-02"
    edit_url = reverse("schedule_cell_edit", args=[class_obj.pk, schedule.pk]) + as_of
    end_url = reverse("schedule_cell_end", args=[class_obj.pk, schedule.pk]) + as_of
    matrix_url = reverse("schedule_weekly", args=[class_obj.pk]) + as_of

    edit_response = client.get(edit_url, HTTP_HX_REQUEST="true")
    end_response = client.get(end_url, HTTP_HX_REQUEST="true")

    assert edit_response.status_code == end_response.status_code == 200
    assert f'action="{edit_url}"'.encode() in edit_response.content
    assert b'hx-target="#schedule-cell-modal-body"' in edit_response.content
    assert b'hx-swap-oob="outerHTML"' in edit_response.content
    assert b'data-bs-dismiss="modal"' in edit_response.content
    assert b"Turma: 1" in edit_response.content
    assert f'action="{end_url}"'.encode() in end_response.content
    assert b"Encerrar aula" in end_response.content
    assert matrix_url.encode() not in edit_response.content
    assert b"<html" not in edit_response.content


@pytest.mark.django_db
def test_schedule_cell_fallback_post_redirects_to_matrix(client, user):
    client.force_login(user)
    class_obj = _class(user)
    teacher, subject = _teacher_with_subject(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    response = client.post(
        reverse("schedule_cell_create", args=[class_obj.pk, Schedule.Day.MON, slot.pk])
        + "?as_of=2026-02-02",
        {
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "room_id": "",
            "valid_from": "2026-02-02",
        },
    )

    assert response.status_code == 302
    assert (
        response["Location"]
        == reverse("schedule_weekly", args=[class_obj.pk]) + "?as_of=2026-02-02"
    )


@pytest.mark.django_db
def test_schedule_cell_create_fallback_get_and_invalid_post_render_form_page(client, user):
    client.force_login(user)
    class_obj = _class(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    url = reverse("schedule_cell_create", args=[class_obj.pk, Schedule.Day.MON, slot.pk])

    get_response = client.get(f"{url}?as_of=2026-02-02")
    invalid_response = client.post(f"{url}?as_of=2026-02-02", {"teacher_id": ""})

    assert get_response.status_code == invalid_response.status_code == 200
    assert b"<!DOCTYPE html>" in get_response.content
    assert b"Adicionar aula" in get_response.content
    assert b"schedule-matrix-workspace" not in get_response.content
    assert b"schedule-matrix-workspace" not in invalid_response.content
    assert reverse("schedule_weekly", args=[class_obj.pk]).encode() in get_response.content
    assert b"Este campo" in invalid_response.content


@pytest.mark.django_db
def test_schedule_day_copy_modal_and_fallback_use_canonical_form_page(client, user):
    client.force_login(user)
    class_obj = _class(user)
    TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    form_url = reverse("schedule_day_copy_form", args=[class_obj.pk]) + "?as_of=2026-02-02"
    copy_url = reverse("schedule_day_copy", args=[class_obj.pk]) + "?as_of=2026-02-02"

    get_response = client.get(form_url)
    modal_response = client.get(form_url, HTTP_HX_REQUEST="true")
    invalid_response = client.post(copy_url, {"source_day": Schedule.Day.MON})
    invalid_modal_response = client.post(
        copy_url,
        {"source_day": Schedule.Day.MON},
        HTTP_HX_REQUEST="true",
    )

    assert get_response.status_code == invalid_response.status_code == 200
    assert b"<!DOCTYPE html>" in get_response.content
    assert b"<!DOCTYPE html>" in invalid_response.content
    assert b"schedule-matrix-workspace" not in get_response.content
    assert b"schedule-matrix-workspace" not in invalid_response.content
    assert f'action="{copy_url}"'.encode() in get_response.content
    assert b'id="schedule-copy-modal-body"' in modal_response.content
    assert b'hx-target="#schedule-copy-modal-body"' in modal_response.content
    assert b'id="schedule-copy-modal-body"' in invalid_modal_response.content
    assert b"Este campo" in invalid_response.content
    assert b"Este campo" in invalid_modal_response.content


@pytest.mark.django_db
def test_schedule_day_copy_fallback_post_redirects_to_selected_matrix(client, user):
    client.force_login(user)
    class_obj = _class(user)
    teacher, subject = _teacher_with_subject(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    ScheduleService(user=user).create_schedule(
        {
            "class_obj_id": class_obj.pk,
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "time_slot_id": slot.pk,
            "day_of_week": Schedule.Day.MON,
            "valid_from": dt.date(2026, 2, 1),
        }
    )

    response = client.post(
        reverse("schedule_day_copy", args=[class_obj.pk]) + "?as_of=2026-02-02",
        {"source_day": Schedule.Day.MON, "target_day": Schedule.Day.TUE, "as_of": "2026-02-06"},
    )

    assert response.status_code == 302
    assert (
        response["Location"]
        == reverse("schedule_weekly", args=[class_obj.pk]) + "?as_of=2026-02-02"
    )


@pytest.mark.django_db
def test_schedule_matrix_cell_actions_are_compact_icons_with_accessible_names(client, user):
    client.force_login(user)
    class_obj = _class(user)
    teacher, subject = _teacher_with_subject(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    ScheduleService(user=user).create_schedule(
        {
            "class_obj_id": class_obj.pk,
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "time_slot_id": slot.pk,
            "day_of_week": Schedule.Day.MON,
            "valid_from": dt.date(2026, 2, 1),
        }
    )

    response = client.get(reverse("schedule_weekly", args=[class_obj.pk]) + "?as_of=2026-02-02")

    assert b'aria-label="Editar aula"' in response.content
    assert b'aria-label="Encerrar aula"' in response.content
    assert b'title="Editar aula"' in response.content
    assert b'title="Encerrar aula"' in response.content
    assert b'class="feather-edit-2"' in response.content
    assert b'class="feather-x"' in response.content


@pytest.mark.django_db
def test_schedule_cell_create_rejects_invalid_day_route_with_not_found(client, user):
    client.force_login(user)
    class_obj = _class(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )

    response = client.get(reverse("schedule_cell_create", args=[class_obj.pk, "INVALID", slot.pk]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_schedule_cell_edit_and_end_fallback_render_form_page_on_get_and_invalid_post(client, user):
    client.force_login(user)
    class_obj = _class(user)
    teacher, subject = _teacher_with_subject(user)
    slot = TimeSlot.objects.create(
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        start_time=dt.time(8),
        end_time=dt.time(9),
        created_by=user,
        updated_by=user,
    )
    schedule = ScheduleService(user=user).create_schedule(
        {
            "class_obj_id": class_obj.pk,
            "teacher_id": teacher.pk,
            "subject_id": subject.pk,
            "time_slot_id": slot.pk,
            "day_of_week": Schedule.Day.MON,
            "valid_from": dt.date(2026, 2, 1),
        }
    )
    edit_url = reverse("schedule_cell_edit", args=[class_obj.pk, schedule.pk]) + "?as_of=2026-02-02"
    end_url = reverse("schedule_cell_end", args=[class_obj.pk, schedule.pk]) + "?as_of=2026-02-02"

    responses = (
        client.get(edit_url),
        client.post(edit_url, {"teacher_id": ""}),
        client.get(end_url),
        client.post(end_url, {"valid_until": ""}),
    )

    assert all(response.status_code == 200 for response in responses)
    assert all(b"<!DOCTYPE html>" in response.content for response in responses)
    assert all(b"schedule-matrix-workspace" not in response.content for response in responses)
    assert b"Editar aula" in responses[0].content
    assert b"Encerrar aula" in responses[2].content
