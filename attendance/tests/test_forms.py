"""Testes dos formulários de frequência."""

import datetime as dt

import pytest

from attendance.forms import JustificationForm
from classes.models import Class, Enrollment
from core.models import CustomUser, Role
from students.models import Student
from students.selectors import StudentSelector
from teachers.models import Teacher


def _student(user, enrollment_number):
    return Student.objects.create(
        first_name="Aluno",
        last_name="Teste",
        birth_date=dt.date(2014, 1, 1),
        enrollment_number=enrollment_number,
        created_by=user,
        updated_by=user,
    )


def _form_data(student):
    return {
        "student": student.pk,
        "start_date": "2026-07-10",
        "end_date": "2026-07-11",
        "reason": "Consulta",
    }


@pytest.mark.django_db
def test_justification_form_accepts_only_injected_students(user):
    eligible = _student(user, "FORM-ELIGIBLE")
    outsider = _student(user, "FORM-OUTSIDER")

    form = JustificationForm(
        _form_data(outsider), student_queryset=Student.objects.filter(pk=eligible.pk)
    )

    assert not form.is_valid()
    assert "student" in form.errors


@pytest.mark.django_db
def test_justification_form_fails_closed_without_injected_queryset(user):
    student = _student(user, "FORM-NO-SCOPE")
    form = JustificationForm(_form_data(student))

    assert not form.is_valid()
    assert "student" in form.errors


@pytest.mark.django_db
def test_justification_student_queryset_limits_teacher_to_assigned_students(user):
    role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
    actor = CustomUser.objects.create_user(
        email="teacher-form-scope@attendance.test",
        password="Senha123",
        role=role,
    )
    teacher = Teacher.objects.create(
        user=actor,
        registration_number="FORM-TEACHER-SCOPE",
        created_by=user,
        updated_by=user,
    )
    assigned_class = Class.objects.create(
        name="FORM-ASSIGNED",
        grade=Class.Grade.ELEMENTARY_1,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=2026,
        class_teacher=teacher,
        created_by=user,
        updated_by=user,
    )
    outsider_class = Class.objects.create(
        name="FORM-OUTSIDER",
        grade=Class.Grade.ELEMENTARY_1,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    assigned = _student(user, "FORM-TEACHER-ASSIGNED")
    outsider = _student(user, "FORM-TEACHER-OUTSIDER")
    for student, class_obj in ((assigned, assigned_class), (outsider, outsider_class)):
        Enrollment.objects.create(
            student=student,
            class_obj=class_obj,
            academic_year=class_obj.academic_year,
            enrollment_date=dt.date.today(),
            status=Enrollment.Status.ACTIVE,
            created_by=user,
            updated_by=user,
        )

    queryset = StudentSelector().eligible_for_justification(actor)

    assert list(queryset.values_list("pk", flat=True)) == [assigned.pk]
