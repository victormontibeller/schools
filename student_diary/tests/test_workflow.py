"""Testes do workflow unidirecional da Agenda escolar."""

import datetime as dt
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, PermissionDeniedError
from core.models import CustomUser, Role, RoleModuleAccess
from guardians.models import Guardian, StudentGuardian
from notifications.models import Notification
from student_diary.models import (
    DiaryCategory,
    DiaryOption,
    DiaryPublishedEntry,
    DiarySheet,
    DiaryViewReceipt,
)
from student_diary.selectors import StudentDiarySelector
from student_diary.services import StudentDiaryService
from student_diary.tests.test_services import _class, _enroll, _payload, _student, _teacher
from student_diary.workflow_services import DiaryWorkflowService


def _saved_sheet(actor, owner):
    teacher = actor.teacher_profile if hasattr(actor, "teacher_profile") else None
    class_obj = _class(owner, teacher)
    student = _student(owner)
    _enroll(owner, class_obj, student)
    StudentDiaryService(user=actor).save_daily_diaries(
        class_obj.pk, dt.date(2026, 7, 15), {str(student.pk): _payload()}
    )
    return DiarySheet.objects.get(), student


def _guardian(owner, student, *, custody=True, suffix="one"):
    role, _ = Role.objects.get_or_create(name=Role.Name.GUARDIAN)
    guardian_user = CustomUser.objects.create_user(
        email=f"guardian-{suffix}@test.com", password="Senha123", role=role
    )
    guardian = Guardian.objects.create(
        user=guardian_user,
        first_name="Responsável",
        email=guardian_user.email,
        created_by=owner,
        updated_by=owner,
    )
    StudentGuardian.objects.create(
        guardian=guardian,
        student=student,
        has_custody=custody,
        created_by=owner,
        updated_by=owner,
    )
    return guardian


def _set_diary_edit(owner, role_name: str, enabled: bool) -> Role:
    role, _ = Role.objects.get_or_create(name=role_name)
    access, _ = RoleModuleAccess.objects.get_or_create(
        role=role,
        module_key="student_diary",
        defaults={"created_by": owner, "updated_by": owner},
    )
    access.can_view = enabled
    access.can_edit = enabled
    access.updated_by = owner
    access.save(update_fields=["can_view", "can_edit", "updated_by", "updated_at"])
    return role


def _role_user(owner, role_name: str, email: str, *, active: bool = True):
    role = Role.objects.get(name=role_name)
    return CustomUser.objects.create_user(
        email=email,
        password="Senha123",
        role=role,
        is_active=active,
        created_by=owner,
        updated_by=owner,
    )


@pytest.mark.django_db
def test_save_creates_draft_and_submit_moves_to_review(user):
    sheet, _student_obj = _saved_sheet(user, user)

    submitted = DiaryWorkflowService(user=user).submit_sheet(sheet.pk)

    assert submitted.status == DiarySheet.Status.PENDING_REVIEW
    assert submitted.submitted_at is not None
    assert submitted.submitted_by == user


@pytest.mark.django_db
def test_workflow_is_blocked_when_school_flag_is_disabled(user, settings, monkeypatch):
    sheet, _student_obj = _saved_sheet(user, user)
    settings.TESTING = False
    monkeypatch.setattr(
        "tenancy.selectors.SchoolSelector.get_current_school",
        lambda _selector: SimpleNamespace(settings={}),
    )

    with pytest.raises(BusinessRuleViolationError):
        DiaryWorkflowService(user=user).submit_sheet(sheet.pk)


@pytest.mark.django_db
def test_submit_rejects_incomplete_roster(user):
    class_obj = _class(user)
    first = _student(user)
    second = _student(user, "DIARY-SECOND")
    _enroll(user, class_obj, first)
    _enroll(user, class_obj, second)
    sheet = DiarySheet.objects.create(
        class_obj=class_obj,
        date=dt.date(2026, 7, 15),
        created_by=user,
        updated_by=user,
    )

    with pytest.raises(BusinessRuleViolationError):
        DiaryWorkflowService(user=user).submit_sheet(sheet.pk)


@pytest.mark.django_db
def test_active_reviewers_require_role_and_student_diary_edit(user):
    _set_diary_edit(user, Role.Name.COORDINATOR, True)
    _set_diary_edit(user, Role.Name.TEACHER, True)
    coordinator = _role_user(user, Role.Name.COORDINATOR, "coord-review@test.com")
    inactive = _role_user(user, Role.Name.COORDINATOR, "coord-inactive@test.com", active=False)
    teacher = _role_user(user, Role.Name.TEACHER, "teacher-review@test.com")
    admin = _role_user(user, Role.Name.ADMIN, "admin-review@test.com")

    reviewers = set(StudentDiarySelector().list_active_reviewers())

    assert {user, coordinator, admin} <= reviewers
    assert inactive not in reviewers
    assert teacher not in reviewers

    _set_diary_edit(user, Role.Name.COORDINATOR, False)
    reviewers = set(StudentDiarySelector().list_active_reviewers())
    assert coordinator not in reviewers
    assert {user, admin} <= reviewers


@pytest.mark.django_db
def test_submit_notifies_only_reviewers_with_student_diary_edit(user):
    _set_diary_edit(user, Role.Name.COORDINATOR, False)
    _set_diary_edit(user, Role.Name.TEACHER, True)
    coordinator = _role_user(user, Role.Name.COORDINATOR, "coord-no-notify@test.com")
    teacher = _role_user(user, Role.Name.TEACHER, "teacher-no-review@test.com")
    admin = _role_user(user, Role.Name.ADMIN, "admin-notify@test.com")
    sheet, _student_obj = _saved_sheet(user, user)

    with patch.object(DiaryWorkflowService, "_schedule_staff_delivery") as schedule:
        DiaryWorkflowService(user=user).submit_sheet(sheet.pk)

    recipients = set(
        Notification.objects.filter(title="Agenda aguardando revisão").values_list(
            "recipient_id", flat=True
        )
    )
    assert recipients == {user.pk, admin.pk}
    assert coordinator.pk not in recipients
    assert teacher.pk not in recipients
    assert {call.args[0] for call in schedule.call_args_list} == recipients


@pytest.mark.django_db
@pytest.mark.parametrize("operation", ["approve", "request_changes", "open"])
def test_coordinator_without_student_diary_edit_cannot_review(user, operation, monkeypatch):
    _set_diary_edit(user, Role.Name.COORDINATOR, False)
    coordinator = _role_user(user, Role.Name.COORDINATOR, f"coord-{operation}@test.com")
    sheet, _student_obj = _saved_sheet(user, user)
    admin_workflow = DiaryWorkflowService(user=user)
    admin_workflow.submit_sheet(sheet.pk)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)
    if operation == "open":
        admin_workflow.approve_sheet(sheet.pk)

    workflow = DiaryWorkflowService(user=coordinator)
    with pytest.raises(PermissionDeniedError):
        if operation == "approve":
            workflow.approve_sheet(sheet.pk)
        elif operation == "request_changes":
            workflow.request_changes(sheet.pk, "Ajustar registro.")
        else:
            workflow.open_sheet_for_correction(sheet.pk)


@pytest.mark.django_db
def test_coordinator_with_student_diary_edit_can_approve(user, monkeypatch):
    _set_diary_edit(user, Role.Name.COORDINATOR, True)
    coordinator = _role_user(user, Role.Name.COORDINATOR, "coord-approve@test.com")
    sheet, _student_obj = _saved_sheet(user, user)
    DiaryWorkflowService(user=user).submit_sheet(sheet.pk)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)

    publication = DiaryWorkflowService(user=coordinator).approve_sheet(sheet.pk)

    assert publication.published_by == coordinator


@pytest.mark.django_db
def test_inactive_coordinator_with_student_diary_edit_cannot_review(user):
    _set_diary_edit(user, Role.Name.COORDINATOR, True)
    coordinator = _role_user(
        user, Role.Name.COORDINATOR, "coord-inactive-review@test.com", active=False
    )
    sheet, _student_obj = _saved_sheet(user, user)
    DiaryWorkflowService(user=user).submit_sheet(sheet.pk)

    with pytest.raises(PermissionDeniedError):
        DiaryWorkflowService(user=coordinator).approve_sheet(sheet.pk)


@pytest.mark.django_db
def test_teacher_cannot_approve_and_admin_may_self_approve(user, monkeypatch):
    from core.permissions import can_access

    _set_diary_edit(user, Role.Name.TEACHER, True)
    teacher = _teacher(user)
    sheet, student = _saved_sheet(teacher.user, user)
    guardian = _guardian(user, student)
    DiaryWorkflowService(user=teacher.user).submit_sheet(sheet.pk)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)

    assert can_access(teacher.user, "student_diary", "edit") is True
    with pytest.raises(PermissionDeniedError):
        DiaryWorkflowService(user=teacher.user).approve_sheet(sheet.pk)
    publication = DiaryWorkflowService(user=user).approve_sheet(sheet.pk)

    sheet.refresh_from_db()
    assert sheet.status == DiarySheet.Status.PUBLISHED
    assert publication.revision_number == 1
    assert publication.entries.count() == 1
    assert DiaryViewReceipt.objects.filter(guardian=guardian).count() == 1
    assert Notification.objects.filter(recipient=guardian.user, source="student_diary").count() == 1


@pytest.mark.django_db
def test_publish_notifies_only_active_custodial_guardians(user, monkeypatch):
    sheet, student = _saved_sheet(user, user)
    custodial = _guardian(user, student, suffix="custody")
    _guardian(user, student, custody=False, suffix="no-custody")
    DiaryWorkflowService(user=user).submit_sheet(sheet.pk)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)

    DiaryWorkflowService(user=user).approve_sheet(sheet.pk)

    assert set(DiaryViewReceipt.objects.values_list("guardian_id", flat=True)) == {custodial.pk}


@pytest.mark.django_db
def test_double_approval_does_not_duplicate_publication(user, monkeypatch):
    sheet, _student_obj = _saved_sheet(user, user)
    DiaryWorkflowService(user=user).submit_sheet(sheet.pk)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)
    service = DiaryWorkflowService(user=user)
    service.approve_sheet(sheet.pk)

    with pytest.raises(BusinessRuleViolationError):
        service.approve_sheet(sheet.pk)

    assert sheet.publications.count() == 1


@pytest.mark.django_db
def test_republish_preserves_first_snapshot(user, monkeypatch):
    sheet, student = _saved_sheet(user, user)
    _guardian(user, student)
    workflow = DiaryWorkflowService(user=user)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)
    workflow.submit_sheet(sheet.pk)
    first = workflow.approve_sheet(sheet.pk)
    first_entry = first.entries.get()
    mood = DiaryCategory.objects.get(name="Humor")
    happy = DiaryOption.objects.get(category=mood, label="Alegre")
    StudentDiaryService(user=user).update_routine_aspect(
        mood.pk,
        {
            "name": "Estado emocional",
            "section": DiaryCategory.Section.MEAL,
            "display_order": 8,
            "is_required": mood.is_required,
            "version": mood.version,
        },
    )
    StudentDiaryService(user=user).update_routine_option(
        mood.pk,
        happy.pk,
        {
            "label": "Muito alegre",
            "display_order": happy.display_order,
            "version": happy.version,
        },
    )
    workflow.open_sheet_for_correction(sheet.pk)
    corrected_payload = _payload(notes="Conteúdo corrigido")
    corrected_payload["answers"][str(mood.pk)] = str(happy.pk)
    StudentDiaryService(user=user).save_daily_diaries(
        sheet.class_obj_id,
        sheet.date,
        {str(student.pk): corrected_payload},
    )
    workflow.submit_sheet(sheet.pk)

    second = workflow.approve_sheet(sheet.pk)

    first_entry.refresh_from_db()
    assert first_entry.notes == "Dia tranquilo."
    first_mood = next(item for item in first_entry.answers_snapshot if item["category"] == "Humor")
    second_mood = next(
        item
        for item in second.entries.get().answers_snapshot
        if item["category"] == "Estado emocional"
    )
    assert first_mood["category"] == "Humor"
    assert first_mood["option"] == "Alegre"
    assert first_mood["section"] == DiaryCategory.Section.ROUTINE
    assert first_mood["display_order"] == 1
    assert second_mood["category"] == "Estado emocional"
    assert second_mood["option"] == "Muito alegre"
    assert second_mood["section"] == DiaryCategory.Section.MEAL
    assert second_mood["display_order"] == 8
    assert second.revision_number == 2
    assert second.entries.get().notes == "Conteúdo corrigido"
    assert (
        Notification.objects.filter(
            source="student_diary", title="Agenda escolar disponível"
        ).count()
        == 2
    )
    assert (
        Notification.objects.filter(
            source="student_diary", title="Agenda aguardando revisão"
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_publish_serializes_custom_routine_item(user, monkeypatch):
    service = StudentDiaryService(user=user)
    aspect = service.create_routine_aspect({"name": "Hidratação", "display_order": 5})
    option = service.create_routine_option(aspect.pk, {"label": "Bebeu bem", "display_order": 1})
    service.set_routine_aspect_enabled(aspect.pk, True, aspect.version)
    class_obj = _class(user)
    student = _student(user)
    _enroll(user, class_obj, student)
    payload = _payload()
    payload["answers"][str(aspect.pk)] = str(option.pk)
    service.save_daily_diaries(class_obj.pk, dt.date(2026, 7, 17), {str(student.pk): payload})
    sheet = DiarySheet.objects.get(class_obj=class_obj)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_staff_delivery", lambda *args: None)
    workflow = DiaryWorkflowService(user=user)

    workflow.submit_sheet(sheet.pk)
    entry = workflow.approve_sheet(sheet.pk).entries.get()

    custom = next(item for item in entry.answers_snapshot if item["category"] == "Hidratação")
    assert custom == {
        "section": DiaryCategory.Section.ROUTINE,
        "category": "Hidratação",
        "option": "Bebeu bem",
        "display_order": 5,
    }


@pytest.mark.django_db
def test_publish_serializes_custom_meal_in_unified_snapshot(user, monkeypatch):
    service = StudentDiaryService(user=user)
    item = service.create_routine_aspect(
        {
            "name": "Ceia",
            "section": DiaryCategory.Section.MEAL,
            "display_order": 4,
            "applies_morning": True,
            "applies_afternoon": False,
            "applies_full": True,
        }
    )
    option = service.create_routine_option(item.pk, {"label": "Aceitou bem", "display_order": 1})
    service.set_routine_aspect_enabled(item.pk, True, item.version)
    class_obj = _class(user)
    student = _student(user)
    _enroll(user, class_obj, student)
    payload = _payload()
    payload["answers"][str(item.pk)] = str(option.pk)
    service.save_daily_diaries(
        class_obj.pk,
        dt.date(2026, 7, 18),
        {str(student.pk): payload},
    )
    sheet = DiarySheet.objects.get(class_obj=class_obj)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_staff_delivery", lambda *args: None)
    workflow = DiaryWorkflowService(user=user)

    workflow.submit_sheet(sheet.pk)
    entry = workflow.approve_sheet(sheet.pk).entries.get()

    custom = next(item for item in entry.answers_snapshot if item["category"] == "Ceia")
    assert custom == {
        "section": DiaryCategory.Section.MEAL,
        "category": "Ceia",
        "option": "Aceitou bem",
        "display_order": 4,
    }


@pytest.mark.django_db
def test_mark_viewed_preserves_first_and_updates_last(user, monkeypatch):
    sheet, student = _saved_sheet(user, user)
    guardian = _guardian(user, student)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)
    workflow = DiaryWorkflowService(user=user)
    workflow.submit_sheet(sheet.pk)
    entry = workflow.approve_sheet(sheet.pk).entries.get()

    first = DiaryWorkflowService(user=guardian.user).mark_entry_viewed(entry.pk)
    first_time = first.first_viewed_at
    second = DiaryWorkflowService(user=guardian.user).mark_entry_viewed(entry.pk)

    assert second.first_viewed_at == first_time
    assert second.last_viewed_at >= first_time
    assert second.view_count == 2
    assert Notification.objects.get(pk=second.notification_id).read_at is not None


@pytest.mark.django_db
def test_revoking_custody_blocks_published_entry(user, monkeypatch):
    sheet, student = _saved_sheet(user, user)
    guardian = _guardian(user, student)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)
    workflow = DiaryWorkflowService(user=user)
    workflow.submit_sheet(sheet.pk)
    entry = workflow.approve_sheet(sheet.pk).entries.get()
    link = StudentGuardian.objects.get(guardian=guardian, student=student)
    link.has_custody = False
    link.save()

    with pytest.raises(ObjectNotFoundError):
        DiaryWorkflowService(user=guardian.user).mark_entry_viewed(entry.pk)


@pytest.mark.django_db
def test_publish_rolls_back_snapshots_when_notification_fails(user, monkeypatch):
    sheet, student = _saved_sheet(user, user)
    _guardian(user, student)
    DiaryWorkflowService(user=user).submit_sheet(sheet.pk)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)

    with (
        patch(
            "notifications.services.NotificationService.create_notification",
            side_effect=RuntimeError("transport unavailable"),
        ),
        pytest.raises(RuntimeError),
    ):
        DiaryWorkflowService(user=user).approve_sheet(sheet.pk)

    sheet.refresh_from_db()
    assert sheet.status == DiarySheet.Status.PENDING_REVIEW
    assert not DiaryPublishedEntry.objects.exists()
