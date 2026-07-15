"""Testes das respostas HTMX da chamada."""

import datetime as dt
import uuid
from unittest.mock import patch

import pytest
from django.urls import reverse

from agenda.models import Schedule, TimeSlot
from attendance.services import AttendanceService
from classes.models import Class, Enrollment
from core.models import CustomUser
from students.models import Student
from teachers.models import Subject, Teacher


@pytest.mark.django_db
def test_attendance_records_list_uses_shared_listing_pattern(client, user):
    client.force_login(user)

    response = client.get(reverse("attendance_records_list"))
    partial_response = client.get(reverse("attendance_records_list"), HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Lista de Frequ" in response.content
    assert b"NOVO" in response.content
    assert partial_response.status_code == 200
    assert b"<html" not in partial_response.content


@pytest.mark.django_db
def test_justifications_list_preserves_status_filter_in_shared_header(client, user):
    client.force_login(user)

    response = client.get(reverse("justifications_list"), {"status": "PENDING"})

    assert response.status_code == 200
    assert b"Lista de Justificativas" in response.content
    assert b'name="status"' in response.content


@pytest.mark.django_db
def test_attendance_fill_post_returns_only_card_for_htmx(client, user):
    client.force_login(user)
    cls = Class.objects.create(
        name="3A",
        grade=Class.Grade.ELEMENTARY_3,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    subject = Subject.objects.create(name="Artes", code="ART", created_by=user, updated_by=user)
    teacher_user = CustomUser.objects.create_user(
        email="attendance-view@example.com",
        password="Senha123",
    )
    teacher = Teacher.objects.create(
        user=teacher_user,
        registration_number="ATT-VIEW",
        created_by=user,
        updated_by=user,
    )
    teacher.subjects.add(subject)
    cls.class_teacher = teacher
    cls.save(update_fields=["class_teacher"])
    slot = TimeSlot.objects.create(
        day_of_week=TimeSlot.Day.MON,
        start_time=dt.time(8),
        end_time=dt.time(9),
        slot_number=1,
        created_by=user,
        updated_by=user,
    )
    Schedule.objects.create(
        class_obj=cls,
        subject=subject,
        teacher=teacher,
        time_slot=slot,
        valid_from=dt.date(2026, 1, 1),
        created_by=user,
        updated_by=user,
    )
    student = Student.objects.create(
        first_name="Aluno",
        last_name="Teste",
        birth_date=dt.date(2015, 1, 1),
        enrollment_number="ATT-STUDENT",
        created_by=user,
        updated_by=user,
    )
    Enrollment.objects.create(
        student=student,
        class_obj=cls,
        enrollment_date=dt.date.today(),
        status=Enrollment.Status.ACTIVE,
        created_by=user,
        updated_by=user,
    )
    record = AttendanceService(user=user).open_attendance(
        {
            "class_id": cls.pk,
            "subject_id": subject.pk,
            "teacher_id": teacher.pk,
            "date": dt.date(2026, 7, 2),
        }
    )

    response = client.post(
        f"/frequencia/{record.pk}/chamada/",
        {f"status_{student.pk}": "ABSENT"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Chamada salva com sucesso" in response.content
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_attendance_summary_student_history_and_risk_views(client, user):
    client.force_login(user)
    cls = Class.objects.create(
        name="5A",
        grade=Class.Grade.ELEMENTARY_5,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    student = Student.objects.create(
        first_name="Histórico",
        last_name="Aluno",
        birth_date=dt.date(2015, 1, 1),
        enrollment_number="ATT-HISTORY",
        created_by=user,
        updated_by=user,
    )
    with (
        patch(
            "attendance.selectors.AttendanceSelector.get_class_attendance_summary",
            return_value={"summary": [], "at_risk": []},
        ),
        patch(
            "attendance.selectors.AttendanceSelector.get_student_attendance",
            return_value=[],
        ),
        patch(
            "attendance.selectors.AttendanceSelector.get_student_attendance_rate",
            return_value=80,
        ),
        patch(
            "attendance.selectors.AttendanceSelector.get_students_at_risk",
            return_value=[],
        ),
    ):
        summary = client.get(reverse("class_attendance_summary", args=[cls.pk]))
        history = client.get(reverse("student_attendance_class", args=[student.pk, cls.pk]))
        risk = client.get(reverse("students_at_risk"), {"class_obj": str(cls.pk)})

    assert summary.status_code == 200
    assert history.status_code == 200
    assert risk.status_code == 200
    assert b"80%" in history.content


@pytest.mark.django_db
def test_justification_create_approve_and_reject_views(client, user):
    client.force_login(user)
    student = Student.objects.create(
        first_name="Justificado",
        last_name="Aluno",
        birth_date=dt.date(2015, 1, 1),
        enrollment_number="ATT-JUSTIFICATION",
        created_by=user,
        updated_by=user,
    )

    create_response = client.post(
        reverse("justification_create"),
        {
            "student": student.pk,
            "start_date": "2026-07-10",
            "end_date": "2026-07-11",
            "reason": "Atestado médico",
        },
    )
    object_id = uuid.uuid4()
    with (
        patch("attendance.services.AttendanceService.approve_justification") as approve,
        patch("attendance.services.AttendanceService.reject_justification") as reject,
    ):
        approve_response = client.post(reverse("justification_approve", args=[object_id]))
        reject_response = client.post(
            reverse("justification_reject", args=[object_id]),
            {"reason": "Documento ilegível"},
        )
        get_response = client.get(reverse("justification_approve", args=[object_id]))

    assert create_response.status_code == 302
    assert approve_response.status_code == 302
    assert reject_response.status_code == 302
    assert get_response.status_code == 302
    approve.assert_called_once_with(object_id)
    reject.assert_called_once_with(object_id, "Documento ilegível")


@pytest.mark.django_db
def test_attendance_fill_returns_404_for_unknown_record(client, user):
    client.force_login(user)

    response = client.get(reverse("attendance_record_fill", args=[uuid.uuid4()]))

    assert response.status_code == 404
