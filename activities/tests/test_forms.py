"""Testes dos formulários do módulo de atividades."""

import datetime as dt

import pytest

from activities.forms import ActivityForm
from agenda.models import Schedule, TimeSlot
from classes.models import Class
from core.models import CustomUser, Role
from teachers.models import Subject, Teacher


@pytest.mark.django_db
def test_activity_form_limits_teacher_options_to_schedule(user):
    role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
    teacher_user = CustomUser.objects.create_user(
        email="activity-form-teacher@test.com",
        password="Senha123",
        first_name="Prof",
        last_name="Grade",
        role=role,
    )
    teacher = Teacher.objects.create(
        user=teacher_user,
        registration_number="ACT-FORM-001",
        created_by=user,
        updated_by=user,
    )
    scheduled_subject = Subject.objects.create(
        name="Matemática",
        code="ACT-FORM-MAT",
        created_by=user,
        updated_by=user,
    )
    unscheduled_subject = Subject.objects.create(
        name="Ciências",
        code="ACT-FORM-CIE",
        created_by=user,
        updated_by=user,
    )
    teacher.subjects.add(scheduled_subject, unscheduled_subject)
    scheduled_class = Class.objects.create(
        name="Atividades 1A",
        grade=Class.Grade.ELEMENTARY_1,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=2025,
        created_by=user,
        updated_by=user,
    )
    unscheduled_class = Class.objects.create(
        name="Atividades 1B",
        grade=Class.Grade.ELEMENTARY_1,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=2025,
        created_by=user,
        updated_by=user,
    )
    time_slot = TimeSlot.objects.create(
        day_of_week=TimeSlot.Day.MON,
        start_time=dt.time(8),
        end_time=dt.time(9),
        slot_number=1,
        created_by=user,
        updated_by=user,
    )
    Schedule.objects.create(
        class_obj=scheduled_class,
        teacher=teacher,
        subject=scheduled_subject,
        time_slot=time_slot,
        valid_from=dt.date(2025, 1, 1),
        created_by=user,
        updated_by=user,
    )

    form = ActivityForm(user=teacher_user)

    assert list(form.fields["teacher"].queryset) == [teacher]
    assert form.fields["teacher"].initial == teacher
    assert form.fields["teacher"].disabled is True
    assert list(form.fields["class_obj"].queryset) == [scheduled_class]
    assert unscheduled_class not in form.fields["class_obj"].queryset
    assert list(form.fields["subject"].queryset) == [scheduled_subject]
    assert unscheduled_subject not in form.fields["subject"].queryset
