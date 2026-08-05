"""Testes das respostas HTMX da chamada."""

import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.urls import reverse

from agenda.models import Schedule, TimeSlot
from attendance.models import AttendanceJustification
from attendance.services import AttendanceService
from audit.models import AuditLog
from base.exceptions import BusinessRuleViolationError
from classes.models import Class, Enrollment
from core.models import CustomUser, Role
from guardians.models import Guardian, StudentGuardian
from students.models import Student
from teachers.models import Subject, Teacher


def _guardian_actor(user, email):
    role, _ = Role.objects.get_or_create(name=Role.Name.GUARDIAN)
    actor = CustomUser.objects.create_user(email=email, password="Senha123", role=role)
    guardian = Guardian.objects.create(
        user=actor, first_name="Responsável", created_by=user, updated_by=user
    )
    return actor, guardian


def _student(user, enrollment_number, last_name):
    return Student.objects.create(
        first_name="Aluno",
        last_name=last_name,
        birth_date=dt.date(2014, 1, 1),
        enrollment_number=enrollment_number,
        created_by=user,
        updated_by=user,
    )


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
        start_time=dt.time(8),
        end_time=dt.time(9),
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        created_by=user,
        updated_by=user,
    )
    Schedule.objects.create(
        class_obj=cls,
        subject=subject,
        teacher=teacher,
        time_slot=slot,
        day_of_week=Schedule.Day.MON,
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
        academic_year=cls.academic_year,
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
    url = reverse("attendance_record_fill", args=[record.pk])

    full_response = client.get(url)

    native_response = client.post(
        url,
        {
            f"status_{student.pk}": "JUSTIFIED",
            f"note_{student.pk}": "Registrado pelo fallback nativo",
        },
    )
    entry = record.entries.get(student=student)

    response = client.post(
        url,
        {f"status_{student.pk}": "ABSENT"},
        HTTP_HX_REQUEST="true",
    )

    full_content = full_response.content.decode()
    content = response.content.decode()
    student_history_url = reverse("student_attendance_class", args=[student.pk, cls.pk])

    assert full_response.status_code == 200
    assert 'class="row g-3 sm-workspace-row sm-workspace-row--mobile-scroll"' in full_content
    assert full_content.count('id="attendance-information-card"') == 1
    assert full_content.count('id="attendance-fill-card"') == 1
    assert "Informações da chamada" in full_content
    assert 'aria-label="Dados da chamada"' in full_content
    assert "Conteúdo ministrado" in full_content
    assert "Observações gerais" in full_content
    assert 'class="card sm-detail-card sm-detail-table-card sm-viewport-card"' in full_content
    assert 'class="card-body p-0 sm-viewport-body"' in full_content
    assert '<h5 class="m-b-10">Chamada</h5>' in full_content
    assert "Lançamento de frequência" in full_content
    assert "Detalhes da aula" not in full_content
    assert "sm-attendance-context" not in full_content
    assert "sm-attendance-lesson-details" not in full_content
    assert "js/sm-floating-dropdowns.js" in full_content
    assert (
        "initializeAttendanceFill(event.target || (event.detail && event.detail.elt));"
        in full_content
    )
    assert teacher.full_name in full_content
    assert teacher_user.email not in full_content
    assert "<noscript>" not in full_content
    assert full_content.count("data-attendance-enhanced\n") == 2
    assert full_content.count("data-attendance-fallback>") == 2
    assert "data-attendance-enhanced\n                                 hidden" in full_content
    assert f'id="status-fallback-{student.pk}"' in full_content
    assert f'id="note-fallback-{student.pk}"' in full_content
    status_fallback = full_content[
        full_content.rfind(
            "<select", 0, full_content.index(f'id="status-fallback-{student.pk}"')
        ) : full_content.index(">", full_content.index(f'id="status-fallback-{student.pk}"'))
    ]
    note_fallback = full_content[
        full_content.rfind(
            "<textarea", 0, full_content.index(f'id="note-fallback-{student.pk}"')
        ) : full_content.index(">", full_content.index(f'id="note-fallback-{student.pk}"'))
    ]
    assert "disabled" not in status_fallback
    assert "disabled" not in note_fallback
    assert (
        f'id="present_{student.pk}" value="PRESENT" autocomplete="off" disabled checked'
        in full_content
    )
    assert f'id="absent_{student.pk}" value="ABSENT" autocomplete="off" disabled' in full_content
    assert f'id="just_{student.pk}" value="JUSTIFIED" autocomplete="off" disabled' in full_content
    assert f'id="note_{student.pk}"' in full_content
    assert full_content.count('rows="6"') == 2
    assert full_content.count('maxlength="250"') == 2
    assert "feather-zap" in full_content
    assert "Melhorar com IA" in full_content
    assert "Em breve" in full_content
    assert (
        'disabled\n                                                aria-disabled="true"'
        in full_content
    )
    assert 'title="Recurso de melhoria de texto em preparação"' in full_content
    assert (
        'maxlength="250"\n                                              disabled></textarea>'
        in full_content
    )
    assert '<option value="PRESENT" selected>' in full_content
    assert native_response.status_code == 302
    assert native_response.url == reverse("attendance_records_list")
    assert entry.status == "JUSTIFIED"
    assert entry.note == "Registrado pelo fallback nativo"
    assert response.status_code == 200
    assert response.templates[0].name == "attendance/partials/attendance_fill_card.html"
    assert "Chamada salva com sucesso" in content
    assert "<html" not in content
    assert "attendance-information-card" not in content
    assert f'href="{student_history_url}"' in content
    assert '<th scope="row" class="sm-attendance-student-column">' in content
    assert content.count("data-sm-floating-dropdown") == 2
    assert content.count(f'name="status_{student.pk}"') == 4
    assert content.count(f'name="note_{student.pk}"') == 2
    assert "data-attendance-status-summary" in content
    assert "data-attendance-note-summary" in content
    assert content.count('class="table-responsive sm-scroll-region"') == 1
    assert 'class="card-footer d-flex justify-content-end gap-2"' in content
    assert content.index('class="card-body p-0 sm-viewport-body"') < content.index(
        'class="table-responsive sm-scroll-region"'
    )
    assert content.rindex("</form>") < content.index(
        'class="card-footer d-flex justify-content-end gap-2"'
    )
    assert 'type="submit" form="attendance-fill-form"' in content


@pytest.mark.django_db
def test_attendance_fill_htmx_renders_service_error_inside_fragment(client, user):
    client.force_login(user)
    record_id = uuid.uuid4()
    class_id = uuid.uuid4()
    student_id = uuid.uuid4()
    student = SimpleNamespace(
        pk=student_id,
        get_full_name=lambda: "Aluno Teste",
        enrollment_number="ATT-ERROR",
    )
    entry = SimpleNamespace(
        student=student,
        student_id=student_id,
        status="PRESENT",
        note="",
    )
    record = SimpleNamespace(
        pk=record_id,
        class_obj=SimpleNamespace(pk=class_id),
        subject="Artes",
        teacher=SimpleNamespace(full_name="Professor"),
        date=dt.date(2026, 7, 2),
        lesson_number=1,
        lesson_content="Conteúdo da aula",
        notes="",
    )

    with (
        patch(
            "attendance.views.AttendanceSelector.get_record_with_entries",
            return_value=(record, [entry]),
        ),
        patch(
            "attendance.views.AttendanceService.record_attendance",
            side_effect=BusinessRuleViolationError("A chamada não aceita novas alterações."),
        ),
    ):
        response = client.post(
            reverse("attendance_record_fill", args=[record_id]),
            {f"status_{student_id}": "PRESENT"},
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert response.status_code == 200
    assert response.templates[0].name == "attendance/partials/attendance_fill_card.html"
    assert "<html" not in content
    assert 'role="alert"' in content
    assert "A chamada não aceita novas alterações." in content


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
def test_guardian_justification_view_lists_only_active_custody_students(client, user):
    actor, guardian = _guardian_actor(user, "guardian-view@attendance.test")
    eligible = _student(user, "VIEW-ELIGIBLE", "Vinculado")
    no_custody = _student(user, "VIEW-NO-CUSTODY", "Sem guarda")
    inactive_link = _student(user, "VIEW-INACTIVE-LINK", "Vínculo inativo")
    StudentGuardian.objects.create(
        student=eligible,
        guardian=guardian,
        has_custody=True,
        created_by=user,
        updated_by=user,
    )
    StudentGuardian.objects.create(
        student=no_custody,
        guardian=guardian,
        has_custody=False,
        created_by=user,
        updated_by=user,
    )
    link = StudentGuardian.objects.create(
        student=inactive_link,
        guardian=guardian,
        has_custody=True,
        created_by=user,
        updated_by=user,
    )
    link.is_active = False
    link.save(update_fields=["is_active", "updated_at"])
    client.force_login(actor)

    response = client.get(reverse("justification_create"))

    assert response.status_code == 200
    assert str(eligible.pk).encode() in response.content
    assert str(no_custody.pk).encode() not in response.content
    assert str(inactive_link.pk).encode() not in response.content


@pytest.mark.django_db
def test_guardian_tampered_justification_post_does_not_write_or_audit(client, user):
    actor, _ = _guardian_actor(user, "guardian-tampered@attendance.test")
    outsider = _student(user, "VIEW-TAMPERED", "Alheio")
    audit_count = AuditLog.objects.count()
    client.force_login(actor)

    response = client.post(
        reverse("justification_create"),
        {
            "student": outsider.pk,
            "start_date": "2026-07-10",
            "end_date": "2026-07-11",
            "reason": "Consulta",
        },
    )

    assert response.status_code == 200
    assert not AttendanceJustification.objects.filter(student=outsider).exists()
    assert AuditLog.objects.count() == audit_count


@pytest.mark.django_db
def test_attendance_fill_returns_404_for_unknown_record(client, user):
    client.force_login(user)

    response = client.get(reverse("attendance_record_fill", args=[uuid.uuid4()]))

    assert response.status_code == 404
