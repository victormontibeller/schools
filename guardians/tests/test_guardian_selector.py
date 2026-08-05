"""Contratos do escopo canônico de alunos sob guarda."""

import datetime as dt

import pytest
from django.utils import timezone

from core.models import CustomUser, Role
from guardians.models import Guardian, StudentGuardian
from guardians.selectors import GuardianSelector
from students.models import Student


def _custody_context(user, suffix: str):
    role = Role.objects.get(name=Role.Name.GUARDIAN)
    guardian_user = CustomUser.objects.create_user(
        email=f"guardian-selector-{suffix}@test.com",
        password="Senha123",
        role=role,
    )
    guardian = Guardian.objects.create(
        user=guardian_user,
        first_name="Responsável",
        created_by=user,
        updated_by=user,
    )
    student = Student.objects.create(
        first_name="Aluno",
        last_name="Escopado",
        birth_date=dt.date(2014, 1, 1),
        enrollment_number=f"GUARD-SCOPE-{suffix}",
        created_by=user,
        updated_by=user,
    )
    link = StudentGuardian.objects.create(
        guardian=guardian,
        student=student,
        has_custody=True,
        created_by=user,
        updated_by=user,
    )
    return guardian_user, guardian, student, link


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid_state",
    [
        "without_custody",
        "inactive_link",
        "deleted_link",
        "inactive_guardian",
        "deleted_guardian",
        "inactive_account",
        "deleted_account",
        "inactive_student",
        "deleted_student",
    ],
)
def test_custodial_scope_rejects_every_invalid_link_state(user, invalid_state):
    guardian_user, guardian, student, link = _custody_context(user, invalid_state)
    selector = GuardianSelector()
    assert selector.user_can_access_student(guardian_user.pk, student.pk) is True

    if invalid_state == "without_custody":
        link.has_custody = False
        link.save(update_fields=["has_custody"])
    elif invalid_state == "inactive_link":
        link.is_active = False
        link.save(update_fields=["is_active"])
    elif invalid_state == "deleted_link":
        link.deleted_at = timezone.now()
        link.save(update_fields=["deleted_at"])
    elif invalid_state == "inactive_guardian":
        guardian.is_active = False
        guardian.save(update_fields=["is_active"])
    elif invalid_state == "deleted_guardian":
        guardian.deleted_at = timezone.now()
        guardian.save(update_fields=["deleted_at"])
    elif invalid_state == "inactive_account":
        guardian_user.is_active = False
        guardian_user.save(update_fields=["is_active"])
    elif invalid_state == "deleted_account":
        guardian_user.deleted_at = timezone.now()
        guardian_user.save(update_fields=["deleted_at"])
    elif invalid_state == "inactive_student":
        student.is_active = False
        student.save(update_fields=["is_active"])
    else:
        student.deleted_at = timezone.now()
        student.save(update_fields=["deleted_at"])

    assert list(selector.custodial_student_ids_for_user(guardian_user.pk)) == []
    assert selector.user_can_access_student(guardian_user.pk, student.pk) is False
