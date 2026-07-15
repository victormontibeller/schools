"""Testes das views inline de atividades."""

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from activities.models import Activity, ActivityGroup, ActivityGroupMember, ActivitySubmission
from agenda.models import Schedule, TimeSlot
from classes.models import Class, Enrollment
from core.models import CustomUser
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

    response = client.post(
        f"/activities/{activity.pk}/score/",
        {
            f"score_{student.pk}": "8.50",
            f"feedback_{student.pk}": "Bom trabalho",
        },
    )

    submission.refresh_from_db()
    assert response.status_code == 302
    assert submission.score == Decimal("8.50")
    assert submission.feedback == "Bom trabalho"


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
        day_of_week=TimeSlot.Day.MON,
        start_time=dt.time(8),
        end_time=dt.time(9),
        slot_number=1,
        created_by=user,
        updated_by=user,
    )
    for class_obj in (first_class, second_class):
        Schedule.objects.create(
            class_obj=class_obj,
            subject=subject,
            teacher=teacher,
            time_slot=slot,
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
