"""Prévia, preferências, ciência explícita e destinatários sem conta."""

import pytest
from django.test import Client
from django.urls import reverse

from notifications.announcement_selectors import AnnouncementAudienceSelector, AnnouncementSelector
from notifications.announcement_services import AnnouncementService
from notifications.models import MessageLog, Notification
from notifications.outbox_services import OutboxService
from notifications.tests.test_announcement_workflow import family, publish

pytestmark = pytest.mark.django_db


def test_preview_counts_pending_contacts_and_persists_each_intention(user, school):
    for suffix in ("1", "2"):
        account, guardian, _, _ = family(user, suffix=suffix)
        guardian.user = None
        guardian.email = ""
        guardian.save()
        account.is_active = False
        account.save()
    service = AnnouncementService(user=user)
    draft = service.create_announcement(
        {
            "title": "Comunicado",
            "body": "Privado",
            "audience": "FAMILIES",
            "send_email": True,
        }
    )
    assert AnnouncementAudienceSelector.preview(draft) == {
        "total": 2,
        "inactive": 2,
        "missing_email": 2,
    }
    revision = service.publish_announcement(draft.pk, version=draft.version)
    assert revision.recipients.count() == 2
    assert MessageLog.objects.filter(announcement=draft).count() == 4
    for log in MessageLog.objects.all():
        OutboxService().dispatch(log.pk)
        log.refresh_from_db()
        assert log.reason_code == "account_not_activated"


def test_email_opt_out_keeps_publication_and_internal_notification(user, school):
    account, guardian, _, _ = family(user)
    guardian.accepts_email_notifications = False
    guardian.save()
    draft, _ = publish(user)
    delivery = MessageLog.objects.get(announcement=draft, channel="EMAIL")
    OutboxService().dispatch(delivery.pk)
    delivery.refresh_from_db()
    assert delivery.reason_code == "preference_disabled"
    assert Notification.objects.filter(recipient=account).count() == 1
    assert AnnouncementSelector().detail(draft.pk, account)["revision"]


def test_acknowledgement_requires_explicit_csrf_post(user, school):
    account, _, _, _ = family(user)
    draft, revision = publish(user)
    client = Client(enforce_csrf_checks=True)
    client.force_login(account)
    url = reverse("announcement_acknowledge", args=[revision.pk])
    assert client.get(url).status_code == 405
    assert client.post(url).status_code == 403
    client.get(reverse("announcement_detail", args=[draft.pk]))
    token = client.cookies["csrftoken"].value
    assert client.post(url, {"csrfmiddlewaretoken": token}).status_code == 302
    receipt = revision.recipients.get()
    timestamp = receipt.acknowledged_at
    assert timestamp
    assert client.post(url, {"csrfmiddlewaretoken": token}).status_code == 302
    receipt.refresh_from_db()
    assert receipt.acknowledged_at == timestamp


def test_stale_version_cannot_publish_or_replace_updated_draft(user, school):
    from base.exceptions import BusinessRuleViolationError

    family(user)
    service = AnnouncementService(user=user)
    data = {"title": "Inicial", "body": "Mensagem", "audience": "FAMILIES"}
    draft = service.create_announcement(data)
    original_version = draft.version
    service.update_announcement(draft.pk, {**data, "title": "Atualizado", "version": draft.version})
    with pytest.raises(BusinessRuleViolationError):
        service.publish_announcement(draft.pk, version=original_version)
    assert not draft.revisions.exists()
    assert not MessageLog.objects.exists()


def test_individual_child_context_revokes_when_that_guard_ends(user, school):
    from base.exceptions import PermissionDeniedError

    account, _, _, links = family(user, children=2)
    draft, revision = publish(
        user, audience="INDIVIDUAL", user_ids=[str(account.pk)], student_id=str(links[0].student_id)
    )
    assert revision.recipients.get().student_ids == [str(links[0].student_id)]
    links[0].has_custody = False
    links[0].save()
    with pytest.raises(PermissionDeniedError):
        AnnouncementSelector().detail(draft.pk, account)
    assert links[1].has_custody
