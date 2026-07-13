"""Testes das regras de negócio da Agenda escolar."""

import datetime as dt

import pytest

from base import context
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from classes.models import Class, Enrollment
from core.models import CustomUser, Role
from student_diary.models import (
    DailyDiary,
    DiaryAnswer,
    DiaryCategory,
    DiaryMeal,
    DiaryOption,
)
from student_diary.selectors import StudentDiarySelector
from student_diary.services import StudentDiaryService
from students.models import Student
from teachers.models import Teacher


def _teacher(user, registration="DIARY-TEACHER"):
    role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
    teacher_user = CustomUser.objects.create_user(
        email=f"{registration.lower()}@test.com",
        password="Senha123",
        role=role,
    )
    return Teacher.objects.create(
        user=teacher_user,
        registration_number=registration,
        created_by=user,
        updated_by=user,
    )


def _class(
    user,
    teacher=None,
    shift=Class.Shift.MORNING,
    stage=Class.EducationStage.EARLY_CHILDHOOD,
):
    grade = (
        Class.Grade.EARLY_PRE_2
        if stage == Class.EducationStage.EARLY_CHILDHOOD
        else Class.Grade.ELEMENTARY_1
    )
    return Class.objects.create(
        name=f"Infantil {shift} {Class.objects.count() + 1}",
        grade=grade,
        education_stage=stage,
        shift=shift,
        academic_year=2026,
        class_teacher=teacher,
        created_by=user,
        updated_by=user,
    )


def _student(user, number="DIARY-001"):
    return Student.objects.create(
        first_name="Criança",
        last_name="Teste",
        birth_date=dt.date(2021, 1, 1),
        enrollment_number=number,
        created_by=user,
        updated_by=user,
    )


def _enroll(user, class_obj, student):
    return Enrollment.objects.create(
        class_obj=class_obj,
        student=student,
        enrollment_date=dt.date(2026, 1, 20),
        status=Enrollment.Status.ACTIVE,
        created_by=user,
        updated_by=user,
    )


def _fixed_answers():
    categories = list(
        DiaryCategory.objects.filter(code__isnull=False, is_enabled=True).prefetch_related(
            "options"
        )
    )
    assert len(categories) == 4
    return {str(category.pk): str(category.options.all()[0].pk) for category in categories}


def _payload(*, meals=None, notes="Dia tranquilo."):
    return {
        "answers": _fixed_answers(),
        "meals": meals
        or {
            DiaryMeal.MealType.MORNING_SNACK: DiaryMeal.Status.ATE_WELL,
            DiaryMeal.MealType.LUNCH: DiaryMeal.Status.ATE_PARTIALLY,
        },
        "notes": notes,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("shift", "expected"),
    [
        (Class.Shift.MORNING, {"MORNING_SNACK", "LUNCH"}),
        (Class.Shift.AFTERNOON, {"LUNCH", "AFTERNOON_SNACK"}),
        (Class.Shift.FULL, {"MORNING_SNACK", "LUNCH", "AFTERNOON_SNACK"}),
    ],
)
def test_meals_for_shift_returns_required_meals(shift, expected):
    assert set(StudentDiaryService.meals_for_shift(shift)) == expected


@pytest.mark.django_db
def test_fixed_aspects_have_expected_options():
    expected_counts = {
        DiaryCategory.Aspect.MOOD: 6,
        DiaryCategory.Aspect.REST: 4,
        DiaryCategory.Aspect.BOWEL_MOVEMENT: 4,
        DiaryCategory.Aspect.PARTICIPATION: 3,
    }
    categories = DiaryCategory.objects.filter(code__isnull=False).prefetch_related("options")

    assert {category.code: category.options.count() for category in categories} == (expected_counts)


@pytest.mark.django_db
def test_save_daily_diaries_creates_all_answers_meals_and_audit(user):
    teacher = _teacher(user)
    class_obj = _class(user, teacher)
    student = _student(user)
    _enroll(user, class_obj, student)

    count = StudentDiaryService(user=teacher.user).save_daily_diaries(
        class_obj.pk,
        dt.date(2026, 7, 12),
        {str(student.pk): _payload()},
    )

    diary = DailyDiary.objects.get(student=student)
    assert count == 1
    assert diary.answers.count() == 4
    assert diary.meals.count() == 2
    assert diary.notes == "Dia tranquilo."
    assert diary.teacher == teacher


@pytest.mark.django_db
def test_save_daily_diaries_accepts_not_present_for_meal(user):
    teacher = _teacher(user)
    class_obj = _class(user, teacher)
    student = _student(user)
    _enroll(user, class_obj, student)
    meals = {
        DiaryMeal.MealType.MORNING_SNACK: DiaryMeal.Status.NOT_PRESENT,
        DiaryMeal.MealType.LUNCH: DiaryMeal.Status.NOT_PRESENT,
    }

    StudentDiaryService(user=teacher.user).save_daily_diaries(
        class_obj.pk,
        dt.date(2026, 7, 12),
        {str(student.pk): _payload(meals=meals)},
    )

    assert set(DailyDiary.objects.get().meals.values_list("status", flat=True)) == {
        DiaryMeal.Status.NOT_PRESENT
    }


@pytest.mark.django_db
def test_save_daily_diaries_rolls_back_whole_class_on_student_error(user):
    teacher = _teacher(user)
    class_obj = _class(user, teacher)
    first = _student(user)
    second = _student(user, "DIARY-002")
    _enroll(user, class_obj, first)
    _enroll(user, class_obj, second)
    invalid = _payload()
    invalid["meals"].pop(DiaryMeal.MealType.LUNCH)

    with pytest.raises(ValidationError):
        StudentDiaryService(user=teacher.user).save_daily_diaries(
            class_obj.pk,
            dt.date(2026, 7, 12),
            {str(first.pk): _payload(), str(second.pk): invalid},
        )

    assert DailyDiary.objects.count() == 0


@pytest.mark.django_db
def test_save_daily_diaries_rejects_non_early_childhood_and_night(user):
    teacher = _teacher(user)
    non_childhood = _class(user, teacher, stage=Class.EducationStage.ELEMENTARY_I)
    night = _class(user, teacher, shift=Class.Shift.NIGHT)

    with pytest.raises(BusinessRuleViolationError):
        StudentDiaryService(user=teacher.user).save_daily_diaries(
            non_childhood.pk, dt.date(2026, 7, 12), {}
        )
    with pytest.raises(BusinessRuleViolationError):
        StudentDiaryService(user=teacher.user).save_daily_diaries(
            night.pk, dt.date(2026, 7, 12), {}
        )


@pytest.mark.django_db
def test_save_daily_diaries_rejects_unlinked_teacher(user):
    teacher = _teacher(user)
    other = _teacher(user, "DIARY-OTHER")
    class_obj = _class(user, teacher)

    with pytest.raises(PermissionDeniedError):
        StudentDiaryService(user=other.user).save_daily_diaries(
            class_obj.pk, dt.date(2026, 7, 12), {}
        )


@pytest.mark.django_db
def test_admin_without_teacher_profile_saves_inside_tenant(user):
    role, _ = Role.objects.get_or_create(name=Role.Name.ADMIN)
    admin = CustomUser.objects.create_user(
        email="school-admin@test.com", password="Senha123", role=role
    )
    class_obj = _class(user)
    student = _student(user)
    _enroll(user, class_obj, student)
    token = context.current_tenant.set("school_demo")
    try:
        StudentDiaryService(user=admin).save_daily_diaries(
            class_obj.pk,
            dt.date(2026, 7, 12),
            {str(student.pk): _payload()},
        )
    finally:
        context.current_tenant.reset(token)

    diary = DailyDiary.objects.get()
    assert diary.teacher is None
    assert diary.created_by == admin


@pytest.mark.django_db
def test_toggle_aspect_is_audited_and_legacy_aspect_is_rejected(user):
    from audit.models import AuditLog

    aspect = DiaryCategory.objects.get(code=DiaryCategory.Aspect.MOOD)
    service = StudentDiaryService(user=user)

    service.set_routine_aspect_enabled(aspect.pk, False)
    aspect.refresh_from_db()

    assert not aspect.is_enabled
    assert AuditLog.objects.filter(
        object_id=str(aspect.pk), operation=AuditLog.Operation.UPDATE
    ).exists()
    legacy = DiaryCategory.objects.create(name="Aspecto legado", created_by=user, updated_by=user)
    with pytest.raises(BusinessRuleViolationError):
        service.set_routine_aspect_enabled(legacy.pk, False)


@pytest.mark.django_db
def test_teacher_cannot_toggle_aspect(user):
    teacher = _teacher(user)
    aspect = DiaryCategory.objects.get(code=DiaryCategory.Aspect.MOOD)

    with pytest.raises(PermissionDeniedError):
        StudentDiaryService(user=teacher.user).set_routine_aspect_enabled(aspect.pk, False)


@pytest.mark.django_db
def test_selector_excludes_legacy_aspect_from_new_sheet_but_preserves_history(user):
    teacher = _teacher(user)
    class_obj = _class(user, teacher)
    student = _student(user)
    _enroll(user, class_obj, student)
    legacy = DiaryCategory.objects.create(name="Categoria antiga", created_by=user, updated_by=user)
    old_option = DiaryOption.objects.create(
        category=legacy, label="Resposta antiga", created_by=user, updated_by=user
    )
    diary = DailyDiary.objects.create(
        student=student,
        class_obj=class_obj,
        teacher=teacher,
        date=dt.date(2026, 7, 11),
        created_by=user,
        updated_by=user,
    )
    DiaryAnswer.objects.create(
        diary=diary,
        category=legacy,
        option=old_option,
        created_by=user,
        updated_by=user,
    )
    selector = StudentDiarySelector()

    sheet = selector.build_daily_sheet(
        class_obj.pk, dt.date(2026, 7, 12), (DiaryMeal.MealType.LUNCH,)
    )
    history = selector.list_student_history(student.pk).get()

    assert legacy not in sheet["categories"]
    assert history.answers.get().option == old_option


@pytest.mark.django_db
def test_selectors_raise_for_missing_objects():
    selector = StudentDiarySelector()
    missing = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ObjectNotFoundError):
        selector.get_class(missing)
    with pytest.raises(ObjectNotFoundError):
        selector.get_category(missing)
