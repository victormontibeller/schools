"""Testes dos wrappers Celery de notificações por tenant."""

from unittest.mock import MagicMock, patch

import pytest

from notifications.tasks import (
    notify_audience_all_task,
    send_announcement_email_task,
    send_announcement_whatsapp_task,
    send_diary_email_task,
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
def test_diary_email_task_maps_staff_event_to_generic_message(user):
    transport = MagicMock()
    transport.send_individual.return_value = 1
    with patch("notifications.tasks.get_transport", return_value=transport):
        send_diary_email_task.run("demo", str(user.pk), "review_requested", "https://demo/agenda/")
    args = transport.send_individual.call_args
    assert args.args[0] == user
    assert args.args[1].subject == "Agenda aguardando revisão"
    assert args.args[2] == {"action_url": "https://demo/agenda/"}
    assert args.kwargs["category"] == "student_diary_review_requested"


@pytest.mark.django_db
def test_announcement_tasks_delegate_to_selected_channels(announcement):
    transport = MagicMock()
    transport.send_announcement_batch.return_value = (2, 0)
    with patch("notifications.tasks.get_transport", return_value=transport) as factory:
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
