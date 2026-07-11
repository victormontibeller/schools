"""Testes dos wrappers Celery de notificações por tenant."""

from unittest.mock import MagicMock, patch

import pytest

from notifications.tasks import (
    notify_audience_all_task,
    send_announcement_email_task,
    send_announcement_whatsapp_task,
    send_email_task,
    send_whatsapp_task,
)


@pytest.fixture()
def message_template(db, user):
    from notifications.models import MessageTemplate

    return MessageTemplate.objects.create(
        name="Task template",
        channel=MessageTemplate.Channel.EMAIL,
        subject="Subject",
        body="Body",
        created_by=user,
        updated_by=user,
    )


@pytest.fixture()
def announcement(db, user):
    from notifications.models import Announcement

    return Announcement.objects.create(
        title="Announcement",
        body="Body",
        author=user,
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
def test_send_email_task_handles_missing_and_existing_entities(user, message_template):
    assert (
        send_email_task.run("demo", "00000000-0000-0000-0000-000000000000", message_template.pk)
        is None
    )

    transport = MagicMock()
    transport.send_individual.return_value = 1
    with patch("notifications.tasks._get_transport", return_value=transport):
        send_email_task.run("demo", user.pk, message_template.pk, {"name": "User"})
    transport.send_individual.assert_called_once_with(user, message_template, {"name": "User"})


@pytest.mark.django_db
def test_send_email_task_retries_total_transport_failure(user, message_template):
    transport = MagicMock()
    transport.send_individual.return_value = 0
    with (
        patch("notifications.tasks._get_transport", return_value=transport),
        patch.object(send_email_task, "retry", side_effect=RuntimeError("retry")),
        pytest.raises(RuntimeError, match="retry"),
    ):
        send_email_task.run("demo", user.pk, message_template.pk)


@pytest.mark.django_db
def test_whatsapp_task_uses_sdk_and_records_stub_failure(message_template):
    transport = MagicMock()
    with (
        patch("notifications.tasks._get_transport", return_value=transport),
        patch("notifications.services.AnnouncementService.log_delivery") as log_delivery,
    ):
        send_whatsapp_task.run("demo", "+5511999999999", message_template.pk)
    transport.channel.send.assert_called_once()
    log_delivery.assert_called_once()


@pytest.mark.django_db
def test_announcement_tasks_delegate_to_selected_channels(announcement):
    transport = MagicMock()
    transport.send_announcement_batch.return_value = (2, 0)
    with patch("notifications.tasks._get_transport", return_value=transport) as factory:
        send_announcement_email_task.run("demo", announcement.pk)
        send_announcement_whatsapp_task.run("demo", announcement.pk)
    assert factory.call_args_list[0].args == ("EMAIL",)
    assert factory.call_args_list[1].args == ("WHATSAPP",)
    assert transport.send_announcement_batch.call_count == 2


@pytest.mark.django_db
def test_notify_all_chunks_active_users(user):
    with patch(
        "notifications.services.NotificationService.create_notifications_bulk", return_value=1
    ) as create_bulk:
        notify_audience_all_task.run("demo", "Title", "Message", "corr-id")
    create_bulk.assert_called_once()
    assert create_bulk.call_args.args[0] == [user.pk]
    assert create_bulk.call_args.args[1]["correlation_id"] == "corr-id"
