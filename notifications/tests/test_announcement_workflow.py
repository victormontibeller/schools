"""Jornada real: autoria, audiência, recibos independentes e recuperação."""

import datetime as dt
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from base.exceptions import PermissionDeniedError
from classes.models import Class, Enrollment
from core.models import CustomUser, Role
from guardians.models import Guardian, StudentGuardian
from notifications.announcement_selectors import AnnouncementSelector
from notifications.announcement_services import AnnouncementService
from notifications.models import AnnouncementRecipient, MessageLog, Notification
from notifications.outbox_services import OutboxService
from students.models import Student

pytestmark = pytest.mark.django_db


def family(user, suffix="1", children=1):
    account = CustomUser.objects.create_user(
        email=f"family{suffix}@example.test", role=Role.objects.get(name="GUARDIAN")
    )
    guardian = Guardian.objects.create(user=account, accepts_email_notifications=True)
    cls = Class.objects.create(name=f"Infantil {suffix}", academic_year=2026)
    links = []
    for index in range(children):
        child = Student.objects.create(
            first_name="Criança",
            last_name=suffix,
            birth_date=dt.date(2022, 1, 1),
            enrollment_number=f"{suffix}-{index}",
        )
        Enrollment.objects.create(
            student=child,
            class_obj=cls,
            academic_year=2026,
            enrollment_date=dt.date(2026, 1, 1),
            status="ACTIVE",
        )
        links.append(
            StudentGuardian.objects.create(student=child, guardian=guardian, has_custody=True)
        )
    return account, guardian, cls, links


def publish(user, **overrides):
    service = AnnouncementService(user=user)
    data = {
        "title": "Comunicado privado",
        "body": "Conteúdo pedagógico privado.",
        "audience": "FAMILIES",
        "send_email": True,
        "requires_acknowledgement": True,
    }
    data.update(overrides)
    draft = service.create_announcement(data)
    revision = service.publish_announcement(draft.pk, version=draft.version)
    draft.refresh_from_db()
    return draft, revision


def test_publish_deduplicates_siblings_and_keeps_acknowledgement_independent(user, school, client):
    account, _, _, _ = family(user, children=2)
    draft, revision = publish(user)
    assert revision.recipients.count() == 1
    assert Notification.objects.filter(recipient=account).count() == 1
    assert MessageLog.objects.filter(announcement=draft).count() == 2
    receipt = revision.recipients.get()
    assert len(receipt.student_ids) == 2
    client.force_login(account)
    response = client.get(reverse("announcement_detail", args=[draft.pk]))
    assert response.status_code == 200
    receipt.refresh_from_db()
    assert receipt.first_viewed_at and not receipt.acknowledged_at
    response = client.post(reverse("announcement_acknowledge", args=[revision.pk]))
    assert response.status_code == 302
    receipt.refresh_from_db()
    assert receipt.acknowledged_at
    service = AnnouncementService(user=user)
    draft = service.open_announcement_correction(draft.pk, version=draft.version)
    correction = service.publish_announcement(draft.pk, version=draft.version)
    assert correction.number == 2
    assert not correction.recipients.get().acknowledged_at
    receipt.refresh_from_db()
    assert receipt.acknowledged_at


def test_class_audience_and_guard_revocation_close_detail_and_pending_delivery(
    user, school, client
):
    account, _, cls, links = family(user)
    outsider, _, _, _ = family(user, suffix="2")
    draft, revision = publish(user, audience="CLASSES", class_ids=[str(cls.pk)])
    assert AnnouncementSelector().list_for_user(outsider).total == 0
    with pytest.raises(PermissionDeniedError):
        AnnouncementSelector().detail(draft.pk, outsider)
    link = links[0]
    link.has_custody = False
    link.save()
    with pytest.raises(PermissionDeniedError):
        AnnouncementService(user=account).acknowledge_announcement(revision.pk)
    email = MessageLog.objects.get(announcement=draft, channel="EMAIL")
    with patch("notifications.task_helpers.get_transport") as transport:
        OutboxService().dispatch(email.pk)
    transport.assert_not_called()
    email.refresh_from_db()
    assert email.dispatch_state == "REVOKED"


def test_delivery_retries_same_identity_after_timeout_and_skips_success(user, school):
    from notifications.channels import ChannelResult

    family(user)
    draft, _ = publish(user)
    delivery = MessageLog.objects.get(announcement=draft, channel="EMAIL")
    results = [
        ChannelResult(
            success=False,
            channel="EMAIL",
            recipient_address="",
            retryable=True,
            error_message="provider_unavailable",
        ),
        ChannelResult(
            success=True, channel="EMAIL", recipient_address="", provider_message_id="provider-1"
        ),
    ]
    with patch("notifications.channels.email.EmailChannel.send", side_effect=results) as send:
        OutboxService().dispatch(delivery.pk)
        delivery.refresh_from_db()
        assert delivery.dispatch_state == "RETRY"
        delivery.next_attempt_at = timezone.now() - dt.timedelta(seconds=1)
        delivery.save()
        OutboxService().dispatch(delivery.pk)
        OutboxService().dispatch(delivery.pk)
    assert send.call_count == 2
    assert (
        send.call_args_list[0].kwargs["idempotency_key"]
        == send.call_args_list[1].kwargs["idempotency_key"]
    )
    assert send.call_args_list[0].args == send.call_args_list[1].args
    assert "Conteúdo pedagógico" not in send.call_args.args[2]
    delivery.refresh_from_db()
    assert delivery.status == "SENT" and delivery.dispatch_state == "COMPLETE"


def test_announcement_publish_rolls_back_intentions_if_audit_fails(user, school):
    family(user)
    service = AnnouncementService(user=user)
    draft = service.create_announcement(
        {"title": "Teste", "body": "Mensagem", "audience": "FAMILIES"}
    )
    with patch(
        "notifications.outbox_services.OutboxService._record_audit", side_effect=RuntimeError
    ):
        with pytest.raises(RuntimeError):
            service.publish_announcement(draft.pk, version=draft.version)
    assert not AnnouncementRecipient.objects.exists()
    assert not MessageLog.objects.exists()
    assert not Notification.objects.exists()


@pytest.mark.parametrize("create,edit", [(True, False), (False, True)])
def test_coordinator_capabilities_match_draft_actions(user, school, client, create, edit):
    from django.urls import reverse

    from base.exceptions import PermissionDeniedError
    from core.models import CustomUser, Role, RoleModuleAccess

    actor = CustomUser.objects.create_user(
        email="coord-capability@example.test",
        password="Violeta824",
        role=Role.objects.get(name="COORDINATOR"),
    )
    RoleModuleAccess.objects.filter(role=actor.role, module_key="notifications").update(
        can_view=True, can_create=create, can_edit=edit
    )
    family(user)
    draft, revision = publish(user)
    draft = AnnouncementService(user=user).open_announcement_correction(
        draft.pk, version=draft.version
    )
    client.force_login(actor)
    response = client.get(reverse("announcement_detail", args=[draft.pk]))
    assert response.status_code == 200
    assert ("Editar rascunho" in response.content.decode()) is edit
    assert client.get(reverse("announcement_create")).status_code == (200 if create else 403)
    assert client.get(reverse("announcement_edit", args=[draft.pk])).status_code == (
        200 if edit else 403
    )
    if edit:
        AnnouncementService(user=actor).publish_announcement(draft.pk, version=draft.version)
    else:
        with pytest.raises(PermissionDeniedError):
            AnnouncementService(user=actor).publish_announcement(draft.pk, version=draft.version)
