"""Testes HTTP das políticas de módulo e propriedade do RBAC."""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.urls import reverse

from base import context
from core.access_catalog import DEACTIVATE, EDIT, VIEW, action_for_operation
from core.permissions import (
    can_access,
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
def test_finance_overview_does_not_grant_other_finance_processes(client):
    from core.models import RoleModuleAccess

    secretary = _role_user("SECRETARY", "finance-overview-only@roles.test")
    RoleModuleAccess.objects.filter(role=secretary.role, module_key="finance_overview").update(
        can_view=True
    )
    client.force_login(secretary)

    assert client.get(reverse("finance_dashboard")).status_code == 200
    for route_name in (
        "financial_template_list",
        "contract_list",
        "billing_list",
        "payment_queue",
        "reminder_history",
        "finance_revenue_report",
        "finance_overdue_report",
    ):
        assert client.get(reverse(route_name)).status_code == 403


@pytest.mark.django_db
def test_admin_role_can_access_all_modules(client):
    user = _role_user("ADMIN", "admin-role@roles.test")
    client.force_login(user)
    assert client.get(reverse("teachers_list")).status_code == 200
    assert client.get(reverse("finance_dashboard")).status_code == 200
    assert client.get(reverse("reenrollment_batch")).status_code == 200
    assert client.get(reverse("document_requirement_list")).status_code == 200


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


@pytest.mark.django_db
@pytest.mark.parametrize("role_name", ["TEACHER", "SECRETARY"])
def test_ineligible_role_cannot_list_justifications_or_reach_selector(client, role_name):
    from core.models import RoleModuleAccess

    actor = _role_user(role_name, f"{role_name.lower()}-justifications@roles.test")
    RoleModuleAccess.objects.filter(role=actor.role, module_key="attendance").update(
        can_view=True,
        can_edit=True,
    )
    client.force_login(actor)

    with patch("attendance.views.JustificationSelector.list_justifications") as list_items:
        response = client.get(reverse("justifications_list"), {"q": "motivo privado"})

    assert response.status_code == 403
    assert b"motivo privado" not in response.content
    list_items.assert_not_called()


@pytest.mark.django_db
def test_teacher_cannot_approve_or_reject_justifications_at_http_boundary(client):
    from core.models import RoleModuleAccess

    actor = _role_user("TEACHER", "teacher-justification-actions@roles.test")
    RoleModuleAccess.objects.filter(role=actor.role, module_key="attendance").update(
        can_view=True,
        can_edit=True,
    )
    client.force_login(actor)
    object_id = uuid.uuid4()

    with (
        patch("attendance.views.AttendanceService.approve_justification") as approve,
        patch("attendance.views.AttendanceService.reject_justification") as reject,
    ):
        approve_response = client.post(reverse("justification_approve", args=[object_id]))
        reject_response = client.post(reverse("justification_reject", args=[object_id]))

    assert approve_response.status_code == 403
    assert reject_response.status_code == 403
    approve.assert_not_called()
    reject.assert_not_called()


@pytest.mark.django_db
def test_eligible_coordinator_can_reach_justification_review_routes(client):
    from core.models import RoleModuleAccess

    actor = _role_user("COORDINATOR", "coordinator-justifications@roles.test")
    RoleModuleAccess.objects.filter(role=actor.role, module_key="attendance").update(
        can_view=True,
        can_edit=True,
    )
    client.force_login(actor)
    object_id = uuid.uuid4()

    list_response = client.get(reverse("justifications_list"))
    with (
        patch("attendance.views.AttendanceService.approve_justification") as approve,
        patch("attendance.views.AttendanceService.reject_justification") as reject,
    ):
        approve_response = client.post(reverse("justification_approve", args=[object_id]))
        reject_response = client.post(reverse("justification_reject", args=[object_id]))

    assert list_response.status_code == 200
    assert approve_response.status_code == 302
    assert reject_response.status_code == 302
    approve.assert_called_once_with(object_id)
    reject.assert_called_once_with(object_id, "")


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
@pytest.mark.django_db
def test_can_configure_student_diary_follows_central_role_policy(role_name, expected):
    user = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        access_mode="STANDARD",
        role=SimpleNamespace(name=role_name),
    )
    if role_name == "TEACHER":
        from core.models import CustomUser, Role
        from teachers.models import Teacher

        user = CustomUser.objects.create_user(
            email="policy-teacher@example.test", role=Role.objects.get(name=Role.Name.TEACHER)
        )
        Teacher.objects.create(user=user, registration_number="POLICY-TEACHER")

    token = context.current_tenant.set("school_test") if role_name == "ADMIN" else None
    try:
        assert can_configure_student_diary(user) is expected
    finally:
        if token is not None:
            context.current_tenant.reset(token)


def test_secretary_diary_configuration_does_not_grant_agenda_editing():
    from core.permissions import can_access

    secretary = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        access_mode="STANDARD",
        role=SimpleNamespace(name="SECRETARY"),
    )

    assert can_access(secretary, "diary_configuration", "view") is True
    assert can_access(secretary, "diary_configuration", "create") is True
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
        assert can_access(admin, "finance_overview", VIEW)
        assert can_execute_service(admin, "financeiro", "create_contract", "FinanceService")
    finally:
        context.current_tenant.reset(tenant_token)

    assert not has_unrestricted_tenant_access(admin)


def test_inactive_and_public_privileged_users_cannot_access_school_modules():
    inactive_admin = SimpleNamespace(
        is_authenticated=True,
        is_active=False,
        is_superuser=False,
        role=SimpleNamespace(name="ADMIN"),
    )
    public_superuser = SimpleNamespace(
        is_authenticated=True,
        is_active=True,
        is_superuser=True,
        role=None,
    )

    assert can_access(inactive_admin, "enrollments", VIEW) is False
    assert (
        can_execute_service(
            inactive_admin,
            "enrollments",
            "create_application",
            "EnrollmentApplicationService",
        )
        is False
    )
    assert can_access(public_superuser, "enrollments", VIEW) is False
    assert (
        can_execute_service(
            public_superuser,
            "enrollments",
            "create_application",
            "EnrollmentApplicationService",
        )
        is False
    )


def test_anonymous_and_demo_policies_deny_privileged_operations():
    anonymous = SimpleNamespace(is_authenticated=False, is_superuser=False)
    assert can_access(anonymous, "students", VIEW) is False
    assert (
        can_execute_service(
            None,
            "notifications",
            "create_notification",
            "NotificationService",
        )
        is False
    )
    assert can_configure_student_diary(anonymous) is False
    assert can_edit_student_diary(anonymous) is False

    demo_teacher = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        access_mode="DEMO",
        role=SimpleNamespace(name="TEACHER"),
    )
    assert (
        can_execute_service(demo_teacher, "financeiro", "create_contract", "FinanceService")
        is False
    )
    assert can_execute_service(demo_teacher, "accounts", "change_password") is True


@pytest.mark.parametrize(
    ("method_name", "expected_action"),
    [
        ("link_student", EDIT),
        ("unlink_student", DEACTIVATE),
        ("reconcile", EDIT),
    ],
)
def test_explicit_service_commands_preserve_action_mapping(method_name, expected_action):
    assert action_for_operation(method_name) == expected_action
