"""Testes dos selectors de turmas."""

import pytest

from classes.models import Class
from classes.selectors import ClassSelector


@pytest.mark.django_db
def test_list_classes_orders_grades_by_pedagogical_sequence(user):
    specs = [
        ("Médio", Class.Grade.HIGH_SCHOOL_1, Class.EducationStage.HIGH_SCHOOL),
        ("Infantil", Class.Grade.EARLY_PRE_2, Class.EducationStage.EARLY_CHILDHOOD),
        ("Fundamental 6", Class.Grade.ELEMENTARY_6, Class.EducationStage.ELEMENTARY_II),
        ("Fundamental 1", Class.Grade.ELEMENTARY_1, Class.EducationStage.ELEMENTARY_I),
    ]
    for name, grade, stage in specs:
        Class.objects.create(
            name=name,
            grade=grade,
            education_stage=stage,
            academic_year=2026,
            created_by=user,
            updated_by=user,
        )

    ascending = ClassSelector().list_classes(order_by="grade")
    descending = ClassSelector().list_classes(order_by="-grade")

    assert [class_obj.grade for class_obj in ascending.items] == [
        Class.Grade.EARLY_PRE_2,
        Class.Grade.ELEMENTARY_1,
        Class.Grade.ELEMENTARY_6,
        Class.Grade.HIGH_SCHOOL_1,
    ]
    assert [class_obj.grade for class_obj in descending.items] == list(
        reversed([class_obj.grade for class_obj in ascending.items])
    )


@pytest.mark.django_db
def test_list_classes_keeps_unknown_legacy_grade_last(user):
    Class.objects.create(
        name="Legada",
        grade="Série Experimental",
        education_stage=Class.EducationStage.OTHER,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    Class.objects.create(
        name="Primeiro",
        grade=Class.Grade.ELEMENTARY_1,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )

    result = ClassSelector().list_classes(order_by="-grade")

    assert result.items[-1].grade == "Série Experimental"
