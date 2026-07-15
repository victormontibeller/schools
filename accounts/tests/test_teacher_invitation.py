"""Testes do convite de ativação de professores."""

import pytest

from accounts.services import AccountService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError
from core.models import CustomUser
from teachers.models import Teacher


@pytest.mark.django_db
def test_activate_teacher_invitation_sets_password_and_consumes_token(user):
    invited = CustomUser.objects.create_user(
        email="invited@example.com", first_name="Prof", last_name="Convidado", is_active=False
    )
    invited.set_unusable_password()
    invited.save(update_fields=["password"])
    Teacher.objects.create(
        user=invited,
        registration_number="PRO-2026-999999",
        created_by=user,
        updated_by=user,
    )
    token = AccountService().create_teacher_invitation_token(invited.pk)

    activated = AccountService().activate_teacher_invitation(token, "Violeta824")

    assert activated.is_active is True
    assert activated.check_password("Violeta824")
    with pytest.raises(BusinessRuleViolationError):
        AccountService().activate_teacher_invitation(token, "Violeta824")


@pytest.mark.django_db
def test_activate_teacher_invitation_rejects_invalid_token():
    with pytest.raises(BusinessRuleViolationError):
        AccountService().activate_teacher_invitation("invalido", "Violeta824")


@pytest.mark.django_db
def test_activate_teacher_invitation_rejects_missing_user_and_non_teacher():
    import uuid

    missing_token = AccountService().create_teacher_invitation_token(uuid.uuid4())
    with pytest.raises(ObjectNotFoundError):
        AccountService().activate_teacher_invitation(missing_token, "Violeta824")

    non_teacher = CustomUser.objects.create_user(
        email="non-teacher@example.com", password=None, is_active=False
    )
    token = AccountService().create_teacher_invitation_token(non_teacher.pk)
    with pytest.raises(BusinessRuleViolationError):
        AccountService().activate_teacher_invitation(token, "Violeta824")
