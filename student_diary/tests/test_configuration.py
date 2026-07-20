"""Testes do catálogo configurável de aspectos da rotina."""

import datetime as dt

import pytest

from audit.models import AuditLog
from base.exceptions import (
    BusinessRuleViolationError,
    PermissionDeniedError,
    ValidationError,
)
from student_diary.models import DiaryCategory, DiaryOption
from student_diary.services import StudentDiaryService
from student_diary.tests.test_services import (
    _class,
    _enroll,
    _payload,
    _student,
    _teacher,
)


@pytest.mark.django_db
def test_create_aspect_starts_required_and_inactive_with_audit(user):
    aspect = StudentDiaryService(user=user).create_routine_aspect(
        {"name": "Hidratação", "display_order": 5}
    )

    assert aspect.section == DiaryCategory.Section.ROUTINE
    assert aspect.is_required is True
    assert aspect.is_enabled is False
    assert aspect.applies_morning is True
    assert aspect.applies_afternoon is True
    assert aspect.applies_full is True
    assert AuditLog.objects.filter(
        object_id=str(aspect.pk), operation=AuditLog.Operation.INSERT
    ).exists()


@pytest.mark.django_db
def test_create_aspect_rejects_duplicate_name(user):
    service = StudentDiaryService(user=user)
    service.create_routine_aspect({"name": "Hidratação", "display_order": 5})

    with pytest.raises(ValidationError) as exc_info:
        service.create_routine_aspect({"name": "Hidratação", "display_order": 6})

    assert "name" in exc_info.value.errors


@pytest.mark.django_db
def test_create_meal_item_persists_section_and_selected_shifts(user):
    item = StudentDiaryService(user=user).create_routine_aspect(
        {
            "name": "Ceia",
            "section": DiaryCategory.Section.MEAL,
            "display_order": 4,
            "applies_morning": False,
            "applies_afternoon": False,
            "applies_full": True,
        }
    )

    assert item.section == DiaryCategory.Section.MEAL
    assert item.applies_morning is False
    assert item.applies_afternoon is False
    assert item.applies_full is True


@pytest.mark.django_db
def test_create_item_rejects_catalog_without_any_shift(user):
    with pytest.raises(ValidationError) as exc_info:
        StudentDiaryService(user=user).create_routine_aspect(
            {
                "name": "Ceia",
                "section": DiaryCategory.Section.MEAL,
                "display_order": 4,
                "applies_morning": False,
                "applies_afternoon": False,
                "applies_full": False,
            }
        )

    assert "shifts" in exc_info.value.errors


@pytest.mark.django_db
def test_update_aspect_edits_seeded_item_and_detects_stale_version(user):
    aspect = DiaryCategory.objects.get(name="Humor")
    original_version = aspect.version
    service = StudentDiaryService(user=user)

    updated = service.update_routine_aspect(
        aspect.pk,
        {
            "name": "Estado emocional",
            "display_order": 8,
            "is_required": False,
            "version": original_version,
        },
    )

    assert updated.name == "Estado emocional"
    assert updated.is_required is False
    with pytest.raises(BusinessRuleViolationError):
        service.update_routine_aspect(
            aspect.pk,
            {
                "name": "Humor antigo",
                "display_order": 1,
                "is_required": True,
                "version": original_version,
            },
        )


@pytest.mark.django_db
def test_update_item_changes_section_and_shifts_with_audit(user):
    item = DiaryCategory.objects.get(name="Humor")

    updated = StudentDiaryService(user=user).update_routine_aspect(
        item.pk,
        {
            "name": item.name,
            "section": DiaryCategory.Section.MEAL,
            "display_order": 9,
            "is_required": item.is_required,
            "applies_morning": False,
            "applies_afternoon": True,
            "applies_full": True,
            "version": item.version,
        },
    )

    assert updated.section == DiaryCategory.Section.MEAL
    assert updated.applies_morning is False
    assert updated.applies_afternoon is True
    assert updated.applies_full is True
    assert AuditLog.objects.filter(
        object_id=str(item.pk), operation=AuditLog.Operation.UPDATE
    ).exists()


@pytest.mark.django_db
def test_enable_aspect_requires_an_available_option(user):
    service = StudentDiaryService(user=user)
    aspect = service.create_routine_aspect({"name": "Hidratação", "display_order": 5})

    with pytest.raises(BusinessRuleViolationError):
        service.set_routine_aspect_enabled(aspect.pk, True, aspect.version)

    option = service.create_routine_option(aspect.pk, {"label": "Bebeu bem", "display_order": 1})
    aspect = service.set_routine_aspect_enabled(aspect.pk, True, aspect.version)

    assert aspect.is_enabled is True
    assert option.is_enabled is True


@pytest.mark.django_db
def test_disable_last_option_of_active_aspect_is_rejected(user):
    service = StudentDiaryService(user=user)
    aspect = service.create_routine_aspect({"name": "Hidratação", "display_order": 5})
    option = service.create_routine_option(aspect.pk, {"label": "Bebeu bem", "display_order": 1})
    aspect = service.set_routine_aspect_enabled(aspect.pk, True, aspect.version)

    with pytest.raises(BusinessRuleViolationError):
        service.set_routine_option_enabled(aspect.pk, option.pk, False, option.version)

    option.refresh_from_db()
    assert option.is_enabled is True


@pytest.mark.django_db
def test_update_and_toggle_seeded_option_preserve_audit(user):
    option = DiaryOption.objects.get(category__name="Humor", label="Alegre")
    service = StudentDiaryService(user=user)

    updated = service.update_routine_option(
        option.category_id,
        option.pk,
        {"label": "Muito alegre", "display_order": 9, "version": option.version},
    )
    service.create_routine_option(option.category_id, {"label": "Sereno", "display_order": 10})
    toggled = service.set_routine_option_enabled(
        option.category_id, option.pk, False, updated.version
    )

    assert toggled.is_enabled is False
    assert (
        AuditLog.objects.filter(
            object_id=str(option.pk), operation=AuditLog.Operation.UPDATE
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_teacher_cannot_mutate_routine_catalog(user):
    teacher = _teacher(user)

    with pytest.raises(PermissionDeniedError):
        StudentDiaryService(user=teacher.user).create_routine_aspect(
            {"name": "Hidratação", "display_order": 5}
        )


@pytest.mark.django_db
def test_save_daily_diaries_accepts_blank_optional_aspect(user):
    service = StudentDiaryService(user=user)
    aspect = service.create_routine_aspect(
        {"name": "Hidratação", "display_order": 5, "is_required": False}
    )
    service.create_routine_option(aspect.pk, {"label": "Bebeu bem", "display_order": 1})
    service.set_routine_aspect_enabled(aspect.pk, True, aspect.version)
    class_obj = _class(user)
    student = _student(user)
    _enroll(user, class_obj, student)

    count = service.save_daily_diaries(
        class_obj.pk,
        dt.date(2026, 7, 17),
        {str(student.pk): _payload()},
    )

    assert count == 1
    assert not student.daily_diaries.get().answers.filter(category=aspect).exists()


@pytest.mark.django_db
def test_save_daily_diaries_rejects_blank_required_custom_aspect(user):
    service = StudentDiaryService(user=user)
    aspect = service.create_routine_aspect({"name": "Hidratação", "display_order": 5})
    service.create_routine_option(aspect.pk, {"label": "Bebeu bem", "display_order": 1})
    service.set_routine_aspect_enabled(aspect.pk, True, aspect.version)
    class_obj = _class(user)
    student = _student(user)
    _enroll(user, class_obj, student)

    with pytest.raises(ValidationError) as exc_info:
        service.save_daily_diaries(
            class_obj.pk,
            dt.date(2026, 7, 17),
            {str(student.pk): _payload()},
        )

    assert "answers" in exc_info.value.errors


@pytest.mark.django_db
def test_disabled_selection_is_preserved_but_rejected_for_new_student(user):
    service = StudentDiaryService(user=user)
    aspect = service.create_routine_aspect({"name": "Hidratação", "display_order": 5})
    selected = service.create_routine_option(aspect.pk, {"label": "Bebeu bem", "display_order": 1})
    service.create_routine_option(aspect.pk, {"label": "Bebeu pouco", "display_order": 2})
    service.set_routine_aspect_enabled(aspect.pk, True, aspect.version)
    class_obj = _class(user)
    first = _student(user)
    _enroll(user, class_obj, first)
    first_payload = _payload()
    first_payload["answers"][str(aspect.pk)] = str(selected.pk)

    service.save_daily_diaries(
        class_obj.pk,
        dt.date(2026, 7, 17),
        {str(first.pk): first_payload},
    )
    service.set_routine_option_enabled(aspect.pk, selected.pk, False, selected.version)
    service.save_daily_diaries(
        class_obj.pk,
        dt.date(2026, 7, 17),
        {str(first.pk): first_payload},
    )
    second = _student(user, "DIARY-NEW")
    _enroll(user, class_obj, second)
    second_payload = _payload()
    second_payload["answers"][str(aspect.pk)] = str(selected.pk)

    with pytest.raises(ValidationError):
        service.save_daily_diaries(
            class_obj.pk,
            dt.date(2026, 7, 17),
            {
                str(first.pk): first_payload,
                str(second.pk): second_payload,
            },
        )

    answer = first.daily_diaries.get().answers.get(category=aspect)
    assert answer.option_id == selected.pk


@pytest.mark.django_db
def test_shift_removed_item_preserves_saved_answer_and_rejects_new_student(user):
    service = StudentDiaryService(user=user)
    item = service.create_routine_aspect({"name": "Hidratação", "display_order": 5})
    selected = service.create_routine_option(item.pk, {"label": "Bebeu bem", "display_order": 1})
    item = service.set_routine_aspect_enabled(item.pk, True, item.version)
    class_obj = _class(user)
    first = _student(user)
    _enroll(user, class_obj, first)
    first_payload = _payload()
    first_payload["answers"][str(item.pk)] = str(selected.pk)
    service.save_daily_diaries(
        class_obj.pk,
        dt.date(2026, 7, 18),
        {str(first.pk): first_payload},
    )
    item = service.update_routine_aspect(
        item.pk,
        {
            "name": item.name,
            "section": item.section,
            "display_order": item.display_order,
            "is_required": item.is_required,
            "applies_morning": False,
            "applies_afternoon": True,
            "applies_full": True,
            "version": item.version,
        },
    )
    service.save_daily_diaries(
        class_obj.pk,
        dt.date(2026, 7, 18),
        {str(first.pk): first_payload},
    )
    second = _student(user, "DIARY-SHIFT-NEW")
    _enroll(user, class_obj, second)
    second_payload = _payload()
    second_payload["answers"][str(item.pk)] = str(selected.pk)

    with pytest.raises(ValidationError):
        service.save_daily_diaries(
            class_obj.pk,
            dt.date(2026, 7, 18),
            {str(first.pk): first_payload, str(second.pk): second_payload},
        )

    assert first.daily_diaries.get().answers.get(category=item).option_id == selected.pk
