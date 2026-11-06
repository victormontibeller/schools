"""Autoria nativa, agendamento, anexos e audiência autorizada."""

import datetime as dt
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from base.exceptions import PermissionDeniedError
from base.tests.images import png_upload
from core.models import CustomUser, Role
from notifications.announcement_services import AnnouncementService
from notifications.models import MessageLog
from notifications.outbox_tasks import recover_tenant_communications
from notifications.tests.test_announcement_workflow import family, publish

pytestmark = pytest.mark.django_db


def test_native_author_can_create_preview_and_publish_without_javascript(user, school, client):
    family(user)
    client.force_login(user)
    response = client.post(
        reverse("announcement_create"),
        {"title": "Native", "body": "Mensagem", "audience": "FAMILIES", "send_email": "on"},
    )
    assert response.status_code == 302
    response = client.get(response.url)
    assert response.status_code == 200
    assert "Destinatários previstos" in response.content.decode()
    draft = response.context["announcement"]
    response = client.post(
        reverse("announcement_action", args=[draft.pk]),
        {"action": "publish", "version": draft.version},
    )
    assert response.status_code == 302
    draft.refresh_from_db()
    assert draft.status == "PUBLISHED"
    response = client.get(reverse("announcement_list"), HTTP_HX_REQUEST="true")
    assert response.status_code == 200 and b"Native" in response.content


@pytest.mark.parametrize("role", ["SECRETARY", "FINANCE", "TEACHER", "GUARDIAN"])
def test_non_author_roles_cannot_create_or_publish(user, school, client, role):
    actor = CustomUser.objects.create_user(
        email=f"{role}@example.test", role=Role.objects.get(name=role)
    )
    with pytest.raises(PermissionDeniedError):
        AnnouncementService(user=actor).create_announcement(
            {"title": "Teste", "body": "Mensagem", "audience": "STAFF"}
        )
    client.force_login(actor)
    assert client.get(reverse("announcement_create")).status_code == 403


def test_scheduler_publishes_due_draft_and_cancellation_prevents_publish(user, school):
    family(user)
    service = AnnouncementService(user=user)
    draft = service.create_announcement(
        {"title": "Programado", "body": "Mensagem", "audience": "FAMILIES"}
    )
    future = timezone.now() + dt.timedelta(hours=1)
    draft = service.schedule_announcement(draft.pk, version=draft.version, scheduled_at=future)
    with (
        freeze_time(future + dt.timedelta(seconds=1)),
        patch("notifications.outbox_services.OutboxService.dispatch"),
    ):
        recover_tenant_communications("test_school")
    draft.refresh_from_db()
    assert draft.status == "PUBLISHED"
    draft = service.open_announcement_correction(draft.pk, version=draft.version)
    draft = service.schedule_announcement(draft.pk, version=draft.version, scheduled_at=future)
    draft = service.cancel_announcement_schedule(draft.pk, version=draft.version)
    with (
        freeze_time(future + dt.timedelta(seconds=1)),
        patch("notifications.outbox_services.OutboxService.dispatch"),
    ):
        recover_tenant_communications("test_school")
    assert draft.revisions.count() == 1


def test_attachment_and_old_revision_remain_private_and_immutable(user, school, client):
    account, _, cls, _ = family(user)
    outsider, _, _, _ = family(user, suffix="2")
    service = AnnouncementService(user=user)
    draft = service.create_announcement(
        {
            "title": "Original",
            "body": "Conteúdo original",
            "audience": "CLASSES",
            "class_ids": [str(cls.pk)],
        }
    )
    attachment = service.add_announcement_attachment(draft.pk, png_upload(), version=draft.version)
    draft.refresh_from_db()
    revision = service.publish_announcement(draft.pk, version=draft.version)
    draft.refresh_from_db()
    draft = service.open_announcement_correction(draft.pk, version=draft.version)
    draft = service.update_announcement(
        draft.pk,
        {
            "title": "Rascunho secreto",
            "body": "Novo conteúdo secreto",
            "audience": "CLASSES",
            "class_ids": [str(cls.pk)],
            "version": draft.version,
        },
    )
    service.remove_announcement_attachment(draft.pk, attachment.pk, version=draft.version)
    assert revision.attachments.get().pk == attachment.pk
    client.force_login(account)
    response = client.get(reverse("announcement_list"))
    assert b"Original" in response.content and b"Rascunho secreto" not in response.content
    response = client.get(reverse("announcement_detail", args=[draft.pk]))
    assert b"Novo conte" not in response.content
    assert client.get(reverse("announcement_attachment", args=[attachment.pk])).status_code == 200
    client.force_login(outsider)
    assert client.get(reverse("announcement_attachment", args=[attachment.pk])).status_code == 403


def test_automatic_retry_does_not_need_original_broker_signal(user, school):
    from notifications.channels import ChannelResult

    family(user)
    with patch("notifications.outbox_services.publish_task_after_commit"):
        draft, _ = publish(user)
    with patch(
        "notifications.channels.email.EmailChannel.send",
        return_value=ChannelResult(
            success=True, channel="EMAIL", recipient_address="", provider_message_id="recovered"
        ),
    ):
        recover_tenant_communications("test_school")
    assert MessageLog.objects.get(announcement=draft, channel="EMAIL").status == "SENT"


def test_unknown_delivery_returns_not_found_and_foreign_attachment_is_rejected(user, school):
    import uuid

    from base.exceptions import ObjectNotFoundError
    from notifications.outbox_services import OutboxService

    with pytest.raises(ObjectNotFoundError):
        OutboxService(user=user).request_delivery_retry(uuid.uuid4())
    service = AnnouncementService(user=user)
    draft = service.create_announcement(
        {"title": "Rascunho", "body": "Privado", "audience": "STAFF"}
    )
    with pytest.raises(PermissionDeniedError):
        service.remove_announcement_attachment(draft.pk, uuid.uuid4(), version=draft.version)
