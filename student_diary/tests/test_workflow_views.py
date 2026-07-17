"""Testes HTTP do workflow e da visualização familiar."""

import pytest
from django.urls import reverse

from student_diary.models import DiarySheet, DiaryViewReceipt
from student_diary.tests.test_workflow import _guardian, _saved_sheet
from student_diary.workflow_services import DiaryWorkflowService


@pytest.mark.django_db
def test_submit_and_approve_endpoints_transition_sheet(client, user, monkeypatch):
    sheet, student = _saved_sheet(user, user)
    _guardian(user, student)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)
    client.force_login(user)

    submitted = client.post(reverse("diary_sheet_submit", args=[sheet.pk]))
    approved = client.post(reverse("diary_sheet_approve", args=[sheet.pk]))

    sheet.refresh_from_db()
    assert submitted.status_code == 302
    assert approved.status_code == 302
    assert sheet.status == DiarySheet.Status.PUBLISHED


@pytest.mark.django_db
def test_review_screen_makes_admin_actions_visible(client, user):
    sheet, _student = _saved_sheet(user, user)
    client.force_login(user)

    draft = client.get(
        reverse("diary_daily"),
        {"class_id": sheet.class_obj_id, "date": sheet.date.isoformat()},
    )
    client.post(reverse("diary_sheet_submit", args=[sheet.pk]))
    pending = client.get(
        reverse("diary_daily"),
        {"class_id": sheet.class_obj_id, "date": sheet.date.isoformat()},
    )

    assert b"Enviar para revis" in draft.content
    assert b"Publicar</button>" not in draft.content
    assert b"A\xc3\xa7\xc3\xa3o necess\xc3\xa1ria" in pending.content
    assert b"Publicar</button>" in pending.content
    assert b"Devolver para corre" in pending.content
    assert b"Salvar Agenda" not in pending.content
    assert b"sm-diary-selector" in pending.content
    assert b"<fieldset disabled>" in pending.content


@pytest.mark.django_db
def test_guardian_publication_is_read_only_and_marks_view(client, user, monkeypatch):
    sheet, student = _saved_sheet(user, user)
    guardian = _guardian(user, student)
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)
    workflow = DiaryWorkflowService(user=user)
    workflow.submit_sheet(sheet.pk)
    entry = workflow.approve_sheet(sheet.pk).entries.get()
    client.force_login(guardian.user)

    detail = client.get(reverse("diary_publication_detail", args=[entry.pk]))
    viewed = client.post(reverse("diary_publication_mark_viewed", args=[entry.pk]))

    assert detail.status_code == 200
    assert b'hx-trigger="load"' in detail.content
    assert b'name="message"' not in detail.content
    assert b"Enviar resposta" not in detail.content
    assert viewed.status_code == 204
    assert DiaryViewReceipt.objects.get(entry=entry, guardian=guardian).view_count == 1


@pytest.mark.django_db
def test_publication_view_denies_guardian_without_custody(client, user, monkeypatch):
    sheet, student = _saved_sheet(user, user)
    guardian = _guardian(user, student, custody=False)
    custodial = _guardian(user, student, suffix="allowed")
    monkeypatch.setattr(DiaryWorkflowService, "_schedule_family_delivery", lambda *args: None)
    workflow = DiaryWorkflowService(user=user)
    workflow.submit_sheet(sheet.pk)
    entry = workflow.approve_sheet(sheet.pk).entries.get()
    assert DiaryViewReceipt.objects.filter(entry=entry, guardian=custodial).exists()
    client.force_login(guardian.user)

    response = client.get(reverse("diary_publication_detail", args=[entry.pk]))

    assert response.status_code == 404
