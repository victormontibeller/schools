"""Regressões finais de autoridade vigente e revogação em camadas canônicas."""

import datetime as dt

import pytest
from django.urls import reverse

from academic_calendar.models import CalendarEvent
from academic_calendar.selectors import CalendarSelector
from academic_calendar.services import CalendarService
from accounts.services import AccountService
from accounts.staff_services import StaffAccountService
from base.exceptions import PermissionDeniedError
from core.access.services import AccessConfigurationService
from core.access_selectors import ObjectAccessSelector
from core.models import CustomUser, Role
from core.permissions import can_access
from core.tests.test_access_configuration import _current_matrix_state
from teachers.models import Subject, Teacher
from teachers.selectors import SubjectSelector
from teachers.services import TeacherService

pytestmark = pytest.mark.django_db


def test_deactivated_teacher_loses_session_selectors_and_service_authority(user, client):
    actor = CustomUser.objects.create_user(
        email="teacher-final@example.test",
        password="Violeta824",
        role=Role.objects.get(name="TEACHER"),
    )
    teacher = Teacher.objects.create(
        user=actor, registration_number="FINAL", hire_date=dt.date(2020, 1, 1)
    )
    subject = Subject.objects.create(name="Rotina")
    teacher.subjects.add(subject)
    event = CalendarEvent.objects.create(
        title="Privado", start_date=dt.date.today(), end_date=dt.date.today(), type="MEETING"
    )
    client.force_login(actor)
    assert can_access(actor, "subjects")
    TeacherService(user=user).deactivate_teacher(teacher.pk)
    assert not can_access(actor, "subjects")
    assert not ObjectAccessSelector.teacher_can_access_subject(actor.pk, subject.pk)
    assert not SubjectSelector.teacher_can_access_subject(actor.pk, subject.pk)
    assert SubjectSelector().list_subjects(user_id=actor.pk, role_name="TEACHER").total == 0
    assert (
        not CalendarSelector()
        .get_events_by_month(event.start_date.year, event.start_date.month, user=actor)
        .exists()
    )
    for name, args in [
        ("subjects_list", []),
        ("subject_detail", [subject.pk]),
        ("calendar_month", []),
    ]:
        assert client.get(reverse(name, args=args)).status_code == 403
    with pytest.raises(PermissionDeniedError):
        CalendarService(user=actor).create_event(
            {
                "title": "X",
                "start_date": dt.date.today(),
                "end_date": dt.date.today(),
                "type": "MEETING",
            }
        )


@pytest.mark.parametrize(
    "command", ["update", "deactivate", "restore", "create", "invite", "matrix"]
)
def test_stale_administrator_is_reauthorized_after_administration_lock(user, command):
    actor = CustomUser.objects.create_user(
        email="old-admin@example.test", password="Violeta824", role=Role.objects.get(name="ADMIN")
    )
    stale = CustomUser.objects.select_related("role").get(pk=actor.pk)
    pending = StaffAccountService(user=user).create_staff_user(
        {
            "first_name": "Pessoa",
            "last_name": "Fictícia",
            "email": "pending-final@example.test",
            "role_name": "SECRETARY",
        }
    )
    AccountService(user=user).update_user(
        actor.pk, {"role_id": Role.objects.get(name="SECRETARY").pk}
    )
    matrix, versions = _current_matrix_state()
    with pytest.raises(PermissionDeniedError):
        if command == "update":
            AccountService(user=stale).update_user(actor.pk, {"role_id": user.role_id})
        elif command == "deactivate":
            AccountService(user=stale).deactivate_user(user.pk)
        elif command == "restore":
            AccountService(user=stale).restore_user(actor.pk)
        elif command == "create":
            StaffAccountService(user=stale).create_staff_user(
                {
                    "first_name": "X",
                    "last_name": "Y",
                    "email": "forbidden@example.test",
                    "role_name": "ADMIN",
                }
            )
        elif command == "invite":
            StaffAccountService(user=stale).send_staff_invitation(pending.pk)
        else:
            AccessConfigurationService(user=stale).update_access_matrix(matrix, versions)
    actor.refresh_from_db()
    assert actor.role.name == "SECRETARY"
    assert not CustomUser.objects.filter(email="forbidden@example.test").exists()
