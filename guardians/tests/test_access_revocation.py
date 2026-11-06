"""Integração da revogação de guarda entre domínios na mesma sessão."""

import datetime as dt
from unittest.mock import patch

import pytest
from django.http import HttpResponse
from django.urls import reverse

from core.models import CustomUser, Role, RoleModuleAccess
from guardians.models import Guardian, StudentGuardian
from guardians.services import GuardianService
from students.models import Student


@pytest.mark.django_db
def test_unlink_revokes_students_dashboard_photo_and_finance_in_same_session(client, user):
    role = Role.objects.get(name=Role.Name.GUARDIAN)
    guardian_user = CustomUser.objects.create_user(
        email="guardian-cross-domain@test.com",
        password="Senha123",
        role=role,
    )
    for module_key in ("dashboard", "students", "finance_overview", "finance_billings"):
        RoleModuleAccess.objects.update_or_create(
            role=role,
            module_key=module_key,
            defaults={
                "can_view": True,
                "can_create": False,
                "can_edit": False,
                "can_deactivate": False,
                "created_by": user,
                "updated_by": user,
            },
        )
    guardian = Guardian.objects.create(
        user=guardian_user,
        first_name="Responsável",
        created_by=user,
        updated_by=user,
    )
    student = Student.objects.create(
        first_name="Filho",
        last_name="Revogável",
        birth_date=dt.date(2014, 1, 1),
        enrollment_number="CROSS-REVOKE-1",
        photo="students/test-photo.jpg",
        created_by=user,
        updated_by=user,
    )
    StudentGuardian.objects.create(
        guardian=guardian,
        student=student,
        has_custody=True,
        created_by=user,
        updated_by=user,
    )
    from notifications.announcement_services import AnnouncementService
    from tenancy.models import Domain, School

    school = School.objects.create(schema_name="test_school", name="Escola fictícia")
    Domain.objects.create(tenant=school, domain="school.example.test", is_primary=True)
    with patch("notifications.outbox_services.publish_task_after_commit"):
        service = AnnouncementService(user=user)
        announcement = service.create_announcement(
            {"title": "Comunicado familiar", "body": "Conteúdo permitido", "audience": "FAMILIES"}
        )
        service.publish_announcement(announcement.pk, version=announcement.version)
    client.force_login(guardian_user)

    students_before = client.get(reverse("students_list"))
    dashboard_before = client.get(reverse("dashboard"))
    partial_before = client.get(reverse("school_dashboard_partial"))
    statement_before = client.get(
        reverse("student_financial_statement", kwargs={"student_id": student.pk})
    )
    with patch(
        "students.views.private_file_response",
        return_value=HttpResponse(b"photo", content_type="image/jpeg"),
    ):
        photo_before = client.get(reverse("student_photo", kwargs={"pk": student.pk}))

    assert students_before.status_code == 200
    assert student.get_full_name().encode() in students_before.content
    assert dashboard_before.status_code == 200
    assert dashboard_before.context["data"]["total_students"] == 1
    assert b"Resumo da fam\xc3\xadlia" in dashboard_before.content
    assert reverse("classes_list").encode() not in dashboard_before.content
    assert reverse("students_at_risk").encode() not in dashboard_before.content
    assert reverse("teachers_list").encode() not in dashboard_before.content
    assert reverse("guardians_list").encode() not in dashboard_before.content
    assert reverse("announcement_list").encode() in dashboard_before.content
    assert reverse("notification_list").encode() in dashboard_before.content
    false_announcement_link = (
        f'<a href="{reverse("notification_list")}" class="sm-dashboard-announcement">'
    ).encode()
    assert false_announcement_link not in dashboard_before.content
    assert (
        reverse("announcement_detail", args=[announcement.pk]).encode() in dashboard_before.content
    )
    assert partial_before.status_code == 200
    assert partial_before.context["data"]["total_students"] == 1
    assert statement_before.status_code == 200
    assert photo_before.status_code == 200

    GuardianService(user=user).unlink_student(guardian.pk, student.pk)

    students_after = client.get(reverse("students_list"))
    dashboard_after = client.get(reverse("dashboard"))
    partial_after = client.get(reverse("school_dashboard_partial"))
    statement_after = client.get(
        reverse("student_financial_statement", kwargs={"student_id": student.pk})
    )
    photo_after = client.get(reverse("student_photo", kwargs={"pk": student.pk}))

    assert students_after.status_code == 200
    assert student.get_full_name().encode() not in students_after.content
    assert dashboard_after.status_code == 200
    assert dashboard_after.context["data"]["total_students"] == 0
    assert partial_after.status_code == 200
    assert partial_after.context["data"]["total_students"] == 0
    assert statement_after.status_code == 403
    assert photo_after.status_code == 403
