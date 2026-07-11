"""Testes HTTP das políticas de módulo e propriedade do RBAC."""

import uuid

import pytest
from django.urls import reverse


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
        ("SECRETARY", "teachers_list"),
        ("COORDINATOR", "finance_dashboard"),
        ("TEACHER", "students_list"),
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
def test_guardian_cannot_access_unlinked_student(client):
    user = _role_user("GUARDIAN", "guardian-role@roles.test")
    client.force_login(user)
    assert client.get(reverse("student_profile", kwargs={"pk": uuid.uuid4()})).status_code == 403


@pytest.mark.django_db
def test_teacher_cannot_access_activity_not_owned(client):
    user = _role_user("TEACHER", "teacher-role@roles.test")
    client.force_login(user)
    assert client.get(reverse("activity_detail", kwargs={"pk": uuid.uuid4()})).status_code == 403
