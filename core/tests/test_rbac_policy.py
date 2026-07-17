"""Testes HTTP das políticas de módulo e propriedade do RBAC."""

import uuid
from types import SimpleNamespace

import pytest
from django.urls import reverse

from base import context
from core.permissions import (
    can_access_module,
    can_configure_student_diary,
    can_edit_student_diary,
    can_execute_service,
    has_unrestricted_tenant_access,
)


def _role_user(role_name, email):
    from core.models import CustomUser, Role

    role, _ = Role.objects.get_or_create(name=role_name)
    return CustomUser.objects.create_user(
        email=email,
        password="Senha123",
        first_name="Role",
        last_name="User",
        role=role,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role_name", "denied_url"),
    [
        ("SECRETARY", "finance_dashboard"),
        ("COORDINATOR", "finance_dashboard"),
        ("TEACHER", "teachers_list"),
        ("FINANCE", "teachers_list"),
        ("GUARDIAN", "teachers_list"),
    ],
)
def test_each_restricted_role_receives_403_outside_module(client, role_name, denied_url):
    user = _role_user(role_name, f"{role_name.lower()}@roles.test")
    client.force_login(user)
    assert client.get(reverse(denied_url)).status_code == 403


@pytest.mark.django_db
def test_admin_role_can_access_all_modules(client):
    user = _role_user("ADMIN", "admin-role@roles.test")
    client.force_login(user)
    assert client.get(reverse("teachers_list")).status_code == 200
    assert client.get(reverse("finance_dashboard")).status_code == 200


@pytest.mark.django_db
def test_secretary_can_access_teacher_registry(client):
    user = _role_user("SECRETARY", "secretary-teachers@roles.test")
    client.force_login(user)

    assert client.get(reverse("teachers_list")).status_code == 200


@pytest.mark.django_db
def test_guardian_cannot_access_unlinked_student(client):
    user = _role_user("GUARDIAN", "guardian-role@roles.test")
    client.force_login(user)
    assert client.get(reverse("student_profile", kwargs={"pk": uuid.uuid4()})).status_code == 403


@pytest.mark.django_db
def test_teacher_cannot_access_activity_not_owned(client):
    user = _role_user("TEACHER", "teacher-role@roles.test")
    client.force_login(user)
    assert client.get(reverse("activity_detail", kwargs={"pk": uuid.uuid4()})).status_code == 403


@pytest.mark.parametrize(
    ("role_name", "expected"),
    [
        ("ADMIN", True),
        ("SECRETARY", True),
        ("COORDINATOR", True),
        ("TEACHER", False),
        ("FINANCE", False),
        ("GUARDIAN", False),
    ],
)
def test_can_configure_student_diary_follows_central_role_policy(role_name, expected):
    user = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        access_mode="STANDARD",
        role=SimpleNamespace(name=role_name),
    )

    assert can_configure_student_diary(user) is expected


def test_secretary_diary_configuration_does_not_grant_agenda_editing():
    from core.permissions import can_access

    secretary = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        access_mode="STANDARD",
        role=SimpleNamespace(name="SECRETARY"),
    )

    assert can_access(secretary, "diary_configuration", "view") is True
    assert can_access(secretary, "diary_configuration", "edit") is True
    assert can_access(secretary, "student_diary", "view") is False
    assert can_access(secretary, "student_diary", "edit") is False
    assert can_access(secretary, "rooms", "view") is True
    assert can_access(secretary, "rooms", "create") is True
    assert can_access(secretary, "rooms", "edit") is True
    assert can_access(secretary, "rooms", "deactivate") is False
    assert can_edit_student_diary(secretary) is False


def test_admin_has_unrestricted_access_only_inside_school_tenant():
    admin = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        access_mode="DEMO",
        role=SimpleNamespace(name="ADMIN"),
    )
    tenant_token = context.current_tenant.set("school_demo")
    try:
        assert has_unrestricted_tenant_access(admin)
        assert can_access_module(admin, "financeiro")
        assert can_execute_service(admin, "financeiro", "create_charge")
    finally:
        context.current_tenant.reset(tenant_token)

    assert not has_unrestricted_tenant_access(admin)


def test_anonymous_and_demo_policies_deny_privileged_operations():
    anonymous = SimpleNamespace(is_authenticated=False, is_superuser=False)
    assert can_access_module(anonymous, "students") is False
    assert can_configure_student_diary(anonymous) is False
    assert can_edit_student_diary(anonymous) is False

    demo_teacher = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        access_mode="DEMO",
        role=SimpleNamespace(name="TEACHER"),
    )
    assert can_execute_service(demo_teacher, "financeiro", "create_plan") is False
    assert can_execute_service(demo_teacher, "accounts", "change_password") is True
