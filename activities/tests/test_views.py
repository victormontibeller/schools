"""Testes das views inline de atividades."""

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityGroup, ActivityGroupMember, ActivitySubmission
from agenda.models import Schedule, TimeSlot
from audit.models import AuditLog
from classes.models import Class, Enrollment
from core.models import CustomUser, Role
from teachers.models import Subject, Teacher


def _group_activity(user):
    cls = Class.objects.create(
        name="3A",
        grade=Class.Grade.ELEMENTARY_3,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    subject = Subject.objects.create(
        name="Matemática", code="MAT-GRP", created_by=user, updated_by=user
    )
    teacher_user = CustomUser.objects.create_user(
        email="activity-group-view@example.com", password="Senha123"
    )
    teacher = Teacher.objects.create(
        user=teacher_user,
        registration_number="ACT-GROUP-VIEW",
        created_by=user,
        updated_by=user,
    )
    activity = Activity.objects.create(
        class_obj=cls,
        subject=subject,
        teacher=teacher,
        title="Projeto coletivo",
        modality=Activity.Modality.GROUP,
        due_date=dt.date(2026, 8, 20),
        created_by=user,
        updated_by=user,
    )
    from students.models import Student

    student = Student.objects.create(
        first_name="Aluno",
        last_name="Grupo",
        birth_date=dt.date(2018, 1, 1),
        enrollment_number="ACT-GRP-01",
        created_by=user,
        updated_by=user,
    )
    Enrollment.objects.create(
        class_obj=cls,
        student=student,
        academic_year=cls.academic_year,
        enrollment_date=dt.date(2026, 1, 20),
        status=Enrollment.Status.ACTIVE,
        created_by=user,
        updated_by=user,
    )
    group = ActivityGroup.objects.create(
        activity=activity, name="Equipe A", created_by=user, updated_by=user
    )
    ActivityGroupMember.objects.create(
        activity=activity,
        group=group,
        student=student,
        created_by=user,
        updated_by=user,
    )
    return activity, group, student


@pytest.mark.django_db
def test_activity_edit_get_returns_only_component_for_htmx(client, user):
    client.force_login(user)
    cls = Class.objects.create(
        name="2A",
        grade=Class.Grade.ELEMENTARY_2,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    subject = Subject.objects.create(name="Ciências", code="CIE", created_by=user, updated_by=user)
    teacher_user = CustomUser.objects.create_user(
        email="activity-view@example.com",
        password="Senha123",
    )
    teacher = Teacher.objects.create(
        user=teacher_user,
        registration_number="ACT-VIEW",
        created_by=user,
        updated_by=user,
    )
    activity = Activity.objects.create(
        class_obj=cls,
        subject=subject,
        teacher=teacher,
        title="Experimento",
        due_date=dt.date(2026, 8, 10),
        created_by=user,
        updated_by=user,
    )

    response = client.get(f"/activities/{activity.pk}/editar/", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Cancelar" in response.content
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_activity_group_get_and_post_htmx_replace_groups_card(client, user):
    activity, group, student = _group_activity(user)
    client.force_login(user)

    get_response = client.get(
        f"/activities/{activity.pk}/grupos/{group.pk}/", HTTP_HX_REQUEST="true"
    )
    post_response = client.post(
        f"/activities/{activity.pk}/grupos/{group.pk}/",
        {"name": "Equipe Azul", "students": [student.pk]},
        HTTP_HX_REQUEST="true",
    )

    group.refresh_from_db()
    assert get_response.status_code == 200
    assert b"activity-groups-card" in get_response.content
    assert b"<html" not in get_response.content
    assert post_response.status_code == 200
    assert b"Equipe Azul" in post_response.content
    assert group.name == "Equipe Azul"


@pytest.mark.django_db
def test_activity_group_result_error_stays_in_component(client, user):
    activity, group, _ = _group_activity(user)
    client.force_login(user)

    response = client.post(
        f"/activities/{activity.pk}/grupos/{group.pk}/resultado/",
        {f"group-{group.pk}-score": "", f"group-{group.pk}-feedback": "Texto"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"activity-groups-card" in response.content
    assert b"Este campo" in response.content
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_activity_group_deactivate_htmx_updates_only_card(client, user):
    activity, group, _ = _group_activity(user)
    client.force_login(user)

    response = client.post(
        f"/activities/{activity.pk}/grupos/{group.pk}/desativar/",
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Nenhum grupo cadastrado" in response.content
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_activity_record_score_saves_decimal_value(client, user):
    activity, _, student = _group_activity(user)
    submission = ActivitySubmission.objects.create(
        activity=activity,
        student=student,
        created_by=user,
        updated_by=user,
    )
    client.force_login(user)
    prefix = f"submission-{submission.pk}"

    response = client.post(
        f"/activities/{activity.pk}/score/",
        {
            f"{prefix}-score": "8.50",
            f"{prefix}-feedback": "Bom trabalho",
            f"{prefix}-submission_id": submission.pk,
            f"{prefix}-version": submission.version,
        },
    )

    submission.refresh_from_db()
    assert response.status_code == 302
    assert submission.score == Decimal("8.50")
    assert submission.feedback == "Bom trabalho"


@pytest.mark.django_db
def test_activity_detail_renders_canonical_grade_with_pending_and_zero_score(client, user):
    activity, _, student = _group_activity(user)
    pending = ActivitySubmission.objects.create(
        activity=activity,
        student=student,
        created_by=user,
        updated_by=user,
    )
    client.force_login(user)

    initial = client.get(f"/activities/{activity.pk}/")
    prefix = f"submission-{pending.pk}"
    saved = client.post(
        f"/activities/{activity.pk}/score/",
        {
            f"{prefix}-score": "0",
            f"{prefix}-feedback": "",
            f"{prefix}-submission_id": pending.pk,
            f"{prefix}-version": pending.version,
        },
    )
    rendered = client.get(f"/activities/{activity.pk}/")

    assert initial.status_code == 200
    assert b"sm-page-header" in initial.content
    assert b"Rascunho" in initial.content
    assert saved.status_code == 302
    assert b"1/1 preenchidas" in rendered.content
    assert b"Status</th>" not in rendered.content
    assert b"sm-activity-score-table" in rendered.content
    assert b"sm-activity-score-student-column" in rendered.content
    assert b"sm-activity-score-feedback-column" in rendered.content
    assert b"data-activity-score-feedback" in rendered.content
    assert b"data-activity-score-feedback-fallback" in rendered.content
    assert b">Observa\xc3\xa7\xc3\xa3o</th>" in rendered.content
    assert b"Sem observa\xc3\xa7\xc3\xa3o" in rendered.content
    assert b"Melhorar com IA" in rendered.content
    assert b"Em breve" in rendered.content
    score_card = rendered.content[rendered.content.index(b'id="activity-score-card"') :]
    assert b"activity-scores-launch-form" not in score_card
    assert b'value="0.00"' in rendered.content
    assert b"sm-sticky-table--first-column" in rendered.content
    assert f"/students/{student.pk}/".encode() in rendered.content


@pytest.mark.django_db
def test_activity_launch_scores_htmx_updates_grade_information_and_groups(client, user):
    activity, _, student = _group_activity(user)
    ActivitySubmission.objects.create(
        activity=activity,
        student=student,
        score=Decimal("8.00"),
        submitted_at=timezone.now(),
        created_by=user,
        updated_by=user,
    )
    client.force_login(user)

    response = client.post(
        f"/activities/{activity.pk}/score/launch/",
        {"version": activity.version},
        HTTP_HX_REQUEST="true",
    )

    activity.refresh_from_db()
    assert response.status_code == 200
    assert b"activity-score-card" in response.content
    assert b"activity-information-card" in response.content
    assert b"activity-groups-card" in response.content
    assert b"hx-swap-oob" in response.content
    assert b"Notas lan\xc3\xa7adas oficialmente" in response.content
    assert b"activity-scores-reopen-form" in response.content
    assert activity.score_status == Activity.ScoreStatus.LAUNCHED


@pytest.mark.django_db
@pytest.mark.parametrize("route_name", ["activity_launch_scores", "activity_reopen_scores"])
def test_activity_score_status_routes_reject_user_without_edit_access(client, user, route_name):
    activity, _, _ = _group_activity(user)
    role, _ = Role.objects.get_or_create(name=Role.Name.FINANCE)
    viewer = CustomUser.objects.create_user(
        email=f"{route_name}-finance@example.com",
        password="Senha123",
        role=role,
    )
    audit_count = AuditLog.objects.filter(model_name="Activity", object_id=str(activity.pk)).count()
    client.force_login(viewer)

    response = client.post(
        reverse(route_name, kwargs={"pk": activity.pk}),
        {"version": activity.version, "reason": "Correção autorizada."},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 403
    assert (
        AuditLog.objects.filter(model_name="Activity", object_id=str(activity.pk)).count()
        == audit_count
    )


@pytest.mark.django_db
@pytest.mark.parametrize("route_name", ["activity_launch_scores", "activity_reopen_scores"])
def test_activity_score_status_routes_reject_teacher_outside_scope(client, user, route_name):
    activity, _, _ = _group_activity(user)
    role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
    outsider_user = CustomUser.objects.create_user(
        email=f"{route_name}-outsider@example.com",
        password="Senha123",
        role=role,
    )
    Teacher.objects.create(
        user=outsider_user,
        registration_number=f"{route_name}-OUT",
        created_by=user,
        updated_by=user,
    )
    audit_count = AuditLog.objects.filter(model_name="Activity", object_id=str(activity.pk)).count()
    client.force_login(outsider_user)

    response = client.post(
        reverse(route_name, kwargs={"pk": activity.pk}),
        {"version": activity.version, "reason": "Correção autorizada."},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 403
    assert (
        AuditLog.objects.filter(model_name="Activity", object_id=str(activity.pk)).count()
        == audit_count
    )


@pytest.mark.django_db
def test_activity_reopen_scores_htmx_requires_reason_and_restores_editing(client, user):
    activity, _, student = _group_activity(user)
    submission = ActivitySubmission.objects.create(
        activity=activity,
        student=student,
        created_by=user,
        updated_by=user,
    )
    activity.score_status = Activity.ScoreStatus.LAUNCHED
    activity.scores_launched_at = timezone.now()
    activity.save(update_fields=["score_status", "scores_launched_at"])
    client.force_login(user)

    invalid = client.post(
        f"/activities/{activity.pk}/score/reopen/",
        {"version": activity.version, "reason": ""},
        HTTP_HX_REQUEST="true",
    )
    valid = client.post(
        f"/activities/{activity.pk}/score/reopen/",
        {"version": activity.version, "reason": "Correção necessária."},
        HTTP_HX_REQUEST="true",
    )

    activity.refresh_from_db()
    assert invalid.status_code == 200
    assert b"activity-score-card" in invalid.content
    assert b"activity-information-card" in invalid.content
    assert b"hx-swap-oob" in invalid.content
    assert b"Este campo" in invalid.content
    assert valid.status_code == 200
    assert b"Notas reabertas para edi\xc3\xa7\xc3\xa3o" in valid.content
    assert activity.score_status == Activity.ScoreStatus.DRAFT
    assert activity.scores_launched_at is None
    assert submission.score is None


@pytest.mark.django_db
def test_activity_record_score_htmx_returns_only_grid_card_with_cell_error(client, user):
    activity, _, student = _group_activity(user)
    submission = ActivitySubmission.objects.create(
        activity=activity,
        student=student,
        created_by=user,
        updated_by=user,
    )
    client.force_login(user)
    prefix = f"submission-{submission.pk}"

    response = client.post(
        f"/activities/{activity.pk}/score/",
        {
            f"{prefix}-score": "",
            f"{prefix}-feedback": "Feedback sem nota",
            f"{prefix}-submission_id": submission.pk,
            f"{prefix}-version": submission.version,
        },
        HTTP_HX_REQUEST="true",
    )

    submission.refresh_from_db()
    assert response.status_code == 200
    assert b"activity-score-card" in response.content
    assert b"Informe a nota" in response.content
    assert b"Feedback sem nota" in response.content
    assert b"<html" not in response.content
    assert submission.score is None


@pytest.mark.django_db
def test_activity_edit_htmx_keeps_card_when_class_change_has_results(client, user):
    first_class = Class.objects.create(
        name="4A",
        grade=Class.Grade.ELEMENTARY_4,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    second_class = Class.objects.create(
        name="4B",
        grade=Class.Grade.ELEMENTARY_4,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    subject = Subject.objects.create(
        name="História", code="HIS-EDIT", created_by=user, updated_by=user
    )
    teacher_user = CustomUser.objects.create_user(
        email="activity-edit-result@example.com", password="Senha123"
    )
    teacher = Teacher.objects.create(
        user=teacher_user,
        registration_number="ACT-EDIT-RESULT",
        created_by=user,
        updated_by=user,
    )
    teacher.subjects.add(subject)
    slot = TimeSlot.objects.create(
        start_time=dt.time(8),
        end_time=dt.time(9),
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        created_by=user,
        updated_by=user,
    )
    for class_obj in (first_class, second_class):
        Schedule.objects.create(
            class_obj=class_obj,
            subject=subject,
            teacher=teacher,
            time_slot=slot,
            day_of_week=Schedule.Day.MON,
            valid_from=dt.date(2026, 1, 1),
            created_by=user,
            updated_by=user,
        )
    activity = Activity.objects.create(
        class_obj=first_class,
        subject=subject,
        teacher=teacher,
        title="Atividade avaliada",
        description="Descrição",
        due_date=dt.date(2026, 8, 10),
        created_by=user,
        updated_by=user,
    )
    from students.models import Student

    student = Student.objects.create(
        first_name="Aluno",
        last_name="Avaliado",
        birth_date=dt.date(2015, 1, 1),
        enrollment_number="ACT-EDIT-STUDENT",
        created_by=user,
        updated_by=user,
    )
    ActivitySubmission.objects.create(
        activity=activity,
        student=student,
        score=8,
        submitted_at=timezone.now(),
        created_by=user,
        updated_by=user,
    )
    client.force_login(user)

    response = client.post(
        f"/activities/{activity.pk}/editar/",
        {
            "class_obj": second_class.pk,
            "subject": subject.pk,
            "teacher": teacher.pk,
            "title": activity.title,
            "description": activity.description,
            "type": Activity.Type.HOMEWORK,
            "modality": Activity.Modality.INDIVIDUAL,
            "due_date": "2026-08-10",
            "max_score": "10.00",
            "weight": "1.00",
            "version": activity.version,
        },
        HTTP_HX_REQUEST="true",
    )
    activity.refresh_from_db()

    assert response.status_code == 200
    assert b"activity-information-card" in response.content
    assert b"n\xc3\xa3o pode ser alterada" in response.content
    assert activity.class_obj == first_class
